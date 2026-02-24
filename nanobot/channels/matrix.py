"""Matrix channel implementation using matrix-nio."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any
import time

from loguru import logger
from nio import (
    AsyncClient,
    Event,
    MatrixRoom,
    RoomMessageText,
    RoomMessageMedia,
    RoomEncryptedMedia,
    InviteMemberEvent,
    LoginResponse,
    SyncResponse,
    RoomEncryptedFile,
    RoomEncryptedImage,
    RoomEncryptedVideo,
    RoomEncryptedAudio,
    RoomFile,
    RoomImage,
    RoomVideo,
    RoomAudio,
)

from nanobot.bus.events import OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.config.schema import MatrixConfig


class MatrixChannel(BaseChannel):
    """Matrix channel using matrix-nio AsyncClient."""

    name = "matrix"

    def __init__(self, config: MatrixConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: MatrixConfig = config
        self._client: AsyncClient | None = None
        self._sync_token_file: Path = Path.home() / ".nanobot" / "matrix_sync_token"
        self._bot_user_id: str | None = None
        self._typing_task: asyncio.Task | None = None
        self._typing_keepalive: int = 10000  # milliseconds

    async def start(self) -> None:
        """Start the Matrix client and sync loop."""
        if not self.config.homeserver or not self.config.user_id:
            logger.error("Matrix homeserver or user_id not configured")
            return

        if not self.config.access_token and not self.config.password:
            logger.error("Matrix access_token or password not configured")
            return

        self._running = True

        # Initialize client
        self._client = AsyncClient(
            homeserver=self.config.homeserver,
            user=self.config.user_id,
            device_id=self.config.device_id or None,
        )

        # Set up event handlers
        self._client.add_event_callback(self._on_message, RoomMessageText)
        self._client.add_event_callback(self._on_invite, InviteMemberEvent)

        # Add media event handlers for file attachments
        self._client.add_event_callback(self._on_media, (RoomMessageMedia, RoomEncryptedMedia))

        try:
            # Login if using password
            if not self.config.access_token and self.config.password:
                logger.info("Logging in with password...")
                response = await self._client.login(self.config.password)
                if isinstance(response, LoginResponse):
                    logger.info("Matrix login successful")
                    self._bot_user_id = response.user_id
                else:
                    logger.error("Matrix login failed: {}", response)
                    return
            else:
                # Set access token directly
                self._client.access_token = self.config.access_token
                self._bot_user_id = self.config.user_id

            logger.info("Starting Matrix client for {}", self._bot_user_id)

            # Load sync token if exists
            sync_token = self._load_sync_token()
            if sync_token:
                logger.debug("Loaded sync token: {}...", sync_token[:20])

            # Start syncing
            await self._client.sync_forever(
                timeout=30000, since=sync_token, full_state=False, set_presence="online"
            )

        except Exception as e:
            logger.error("Matrix client error: {}", e)
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the Matrix client."""
        self._running = False

        # Cancel typing task
        if self._typing_task:
            self._typing_task.cancel()
            try:
                await self._typing_task
            except asyncio.CancelledError:
                pass
            self._typing_task = None

        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning("Matrix client close failed: {}", e)
            self._client = None

    async def send(self, msg: OutboundMessage) -> None:
        """Send a message through Matrix with typing indicators."""
        if not self._client:
            logger.warning("Matrix client not running")
            return

        # Start typing indicator for the room
        if msg.chat_id:
            self._start_typing(msg.chat_id)

        try:
            await self._send_message_with_media(msg)
        finally:
            # Stop typing indicator
            if msg.chat_id and self._client and self._client.should_send_presence:
                try:
                    await self._client.user_typing(msg.chat_id, typing_state=False)
                except Exception:
                    pass  # Ignore errors when stopping typing

    async def _send_message_with_media(self, msg: OutboundMessage) -> None:
        """Send a message through Matrix with thread support."""
        if not self._client:
            logger.warning("Matrix client not running")
            return

        try:
            room_id = msg.chat_id
            content = msg.content

            # Extract thread info from metadata if available
            thread_info = (
                msg.metadata.get("matrix", {}).get("thread", None) if msg.metadata else None
            )

            # Split long messages (Matrix has a practical limit around 65KB)
            chunks = self._split_message(content)

            for chunk in chunks:
                # Convert markdown to Matrix HTML format
                formatted_body = self._markdown_to_matrix_html(chunk)

                # Send as formatted message if HTML conversion was applied
                if formatted_body != chunk:
                    message_content = {
                        "msgtype": "m.text",
                        "body": chunk,  # Plain text fallback
                        "format": "org.matrix.custom.html",
                        "formatted_body": formatted_body,
                    }
                else:
                    # Send as plain text
                    message_content = {"msgtype": "m.text", "body": chunk}

                # Add thread relation if available
                if thread_info and thread_info.get("in_reply_to"):
                    message_content["m.relates_to"] = {
                        "m.rel_type": "m.thread",
                        "m.in_reply_to": {
                            "event_id": thread_info["in_reply_to"],
                        },
                        "is_falling_back": thread_info.get("is_falling_back", True),
                    }

                response = await self._client.room_send(
                    room_id=room_id, message_type="m.room.message", content=message_content
                )

                if hasattr(response, "event_id"):
                    logger.debug("Matrix message sent: {}", response.event_id)
                else:
                    logger.warning("Matrix send failed: {}", response)

            # Send media files
            for media_path in msg.media or []:
                try:
                    await self._send_media_with_thread(room_id, media_path, thread_info)
                except Exception as e:
                    logger.error("Failed to send media {}: {}", media_path, e)

        except Exception as e:
            logger.error("Error sending Matrix message: {}", e)

    async def _start_typing(self, room_id: str) -> None:
        """Start typing indicator and keep it alive during processing."""
        if not self._client or not self._client.should_send_presence:
            return

        try:
            await self._client.user_typing(room_id, typing_state=True)
        except Exception as e:
            logger.debug("Failed to start typing indicator: {}", e)
            return

        # Cancel any existing typing task
        if self._typing_task:
            self._typing_task.cancel()
            try:
                await self._typing_task
            except asyncio.CancelledError:
                pass

        # Start new typing keepalive task
        self._typing_task = asyncio.create_task(self._typing_keepalive_loop(room_id))

    async def _typing_keepalive_loop(self, room_id: str) -> None:
        """Keep typing indicator alive during processing."""
        while self._running and self._client and self._client.should_send_presence:
            try:
                await self._client.user_typing(room_id, typing_state=True)
                await asyncio.sleep(self._typing_keepalive / 1000)  # Convert to seconds
            except Exception:
                break

    async def _send_media_with_thread(
        self, room_id: str, file_path: str, thread_info: dict | None = None
    ) -> None:
        """Send a media file to a Matrix room with thread support."""
        if not self._client:
            return

        try:
            path = Path(file_path)
            if not path.exists():
                logger.error("Media file not found: {}", file_path)
                return

            mime_type = self._guess_mime_type(path.suffix)

            # Apply media size limit if configured
            max_bytes = self.config.maxMediaBytes
            if max_bytes > 0:
                file_size = path.stat().st_size
                if file_size > max_bytes:
                    logger.warning(
                        "Media file {} too large: {} bytes > {} bytes limit",
                        file_path,
                        file_size,
                        max_bytes,
                    )
                    return

            with open(path, "rb") as f:
                response = await self._client.upload(
                    data_provider=f.read, content_type=mime_type, filename=path.name
                )

            if hasattr(response, "content_uri"):
                # Send the uploaded file as a message
                content = {
                    "msgtype": "m.file",
                    "body": path.name,
                    "url": response.content_uri,
                    "info": {"size": path.stat().st_size, "mimetype": mime_type},
                }

                # Use specific message types for images/videos/audio
                if mime_type.startswith("image/"):
                    content["msgtype"] = "m.image"
                elif mime_type.startswith("video/"):
                    content["msgtype"] = "m.video"
                elif mime_type.startswith("audio/"):
                    content["msgtype"] = "m.audio"

                # Add thread relation if available
                if thread_info and thread_info.get("in_reply_to"):
                    content["m.relates_to"] = {
                        "m.rel_type": "m.thread",
                        "m.in_reply_to": {
                            "event_id": thread_info["in_reply_to"],
                        },
                        "is_falling_back": thread_info.get("is_falling_back", True),
                    }

                await self._client.room_send(
                    room_id=room_id, message_type="m.room.message", content=content
                )
                logger.debug("Matrix media sent with thread relation: {}", path.name)
            else:
                logger.error("Matrix media upload failed: {}", response)

        except Exception as e:
            logger.error("Error uploading media to Matrix: {}", e)

    async def _send_media(self, room_id: str, file_path: str) -> None:
        """Send a media file to a Matrix room."""
        if not self._client:
            return

        try:
            path = Path(file_path)
            if not path.exists():
                logger.error("Media file not found: {}", file_path)
                return

            mime_type = self._guess_mime_type(path.suffix)

            with open(path, "rb") as f:
                response = await self._client.upload(
                    data_provider=f.read, content_type=mime_type, filename=path.name
                )

            if hasattr(response, "content_uri"):
                # Send the uploaded file as a message
                content = {
                    "msgtype": "m.file",
                    "body": path.name,
                    "url": response.content_uri,
                    "info": {"size": path.stat().st_size, "mimetype": mime_type},
                }

                # Use specific message types for images/videos/audio
                if mime_type.startswith("image/"):
                    content["msgtype"] = "m.image"
                elif mime_type.startswith("video/"):
                    content["msgtype"] = "m.video"
                elif mime_type.startswith("audio/"):
                    content["msgtype"] = "m.audio"

                await self._client.room_send(
                    room_id=room_id, message_type="m.room.message", content=content
                )
                logger.debug("Matrix media sent: {}", path.name)
            else:
                logger.error("Matrix media upload failed: {}", response)

        except Exception as e:
            logger.error("Error uploading media to Matrix: {}", e)

    async def _on_message(self, room: MatrixRoom, event: RoomMessageText) -> None:
        """Handle incoming text messages."""
        if not self._running:
            return

        # Ignore messages from the bot itself
        if event.sender == self._bot_user_id:
            return

        # Ignore messages that are too old (avoid processing old messages on restart)
        if hasattr(event, "server_timestamp"):
            import time

            if (time.time() * 1000 - event.server_timestamp) > 30000:  # 30 seconds
                return

        sender_id = event.sender
        chat_id = room.room_id
        content = event.body

        logger.debug(
            "Matrix message: room={} sender={} type={} content={}...",
            room.display_name or room.room_id,
            sender_id,
            room.join_rule,
            content[:50],
        )

        # Check if this message should be processed based on room policy
        if not self._should_respond_in_room(room, event):
            return

        # Strip bot mention from message
        content = self._strip_bot_mention(content)

        # Extract thread information if available
        thread_info = self._extract_thread_info(event)

        # Save sync token after processing message
        if self._client and hasattr(self._client, "next_batch"):
            self._save_sync_token(self._client.next_batch)

        try:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=content,
                metadata={
                    "matrix": {
                        "event_id": event.event_id,
                        "room_name": room.display_name,
                        "room_type": "dm" if room.member_count == 2 else "room",
                        "member_count": room.member_count,
                        "join_rule": room.join_rule,
                        "thread": thread_info,
                    }
                },
            )
        except Exception:
            logger.exception("Error handling Matrix message from {}", sender_id)

    async def _on_media(
        self, room: MatrixRoom, event: RoomMessageMedia | RoomEncryptedMedia
    ) -> None:
        """Handle incoming media attachments (files, images, videos, audio)."""
        if not self._running:
            return

        # Ignore messages from the bot itself
        if hasattr(event, "sender") and event.sender == self._bot_user_id:
            return

        # Ignore messages that are too old
        if hasattr(event, "server_timestamp"):
            if (time.time() * 1000 - event.server_timestamp) > 30000:  # 30 seconds
                return

        sender_id = event.sender
        chat_id = room.room_id

        logger.debug(
            "Matrix media: room={} sender={} type={} content={}...",
            room.display_name or room.room_id,
            sender_id,
            getattr(event, "msgtype", "unknown"),
            "media attachment",
        )

        # Check if this message should be processed based on room policy
        if not self._should_respond_in_room(room, event):
            return

        # Extract media information
        media_info = self._extract_media_info(event)
        if not media_info:
            logger.warning("Could not extract media info from event")
            return

        # Save sync token after processing message
        if self._client and hasattr(self._client, "next_batch"):
            self._save_sync_token(self._client.next_batch)

        try:
            await self._handle_message(
                sender_id=sender_id,
                chat_id=chat_id,
                content=f"[{media_info['type']}] {media_info.get('caption', '')}",
                metadata={
                    "matrix": {
                        "event_id": event.event_id,
                        "room_name": room.display_name,
                        "room_type": "dm" if room.member_count == 2 else "room",
                        "member_count": room.member_count,
                        "join_rule": room.join_rule,
                        "media": media_info,
                    }
                },
            )
        except Exception:
            logger.exception("Error handling Matrix media from {}", sender_id)

    def _extract_media_info(self, event: RoomMessageMedia | RoomEncryptedMedia) -> dict | None:
        """Extract information from media events."""
        try:
            media_info = {
                "type": getattr(event, "msgtype", "unknown"),
                "filename": getattr(event, "body", ""),
                "size": None,
            }

            # Handle encrypted media
            if isinstance(event, RoomEncryptedMedia):
                if hasattr(event, "file") and event.file:
                    media_info.update(
                        {
                            "url": event.file.url,
                            "size": event.file.size,
                            "mimetype": event.file.mimetype,
                        }
                    )
                elif hasattr(event, "url"):
                    media_info["url"] = event.url
            else:
                # Handle unencrypted media
                if hasattr(event, "url"):
                    media_info["url"] = event.url
                if hasattr(event, "info") and event.info:
                    media_info.update(
                        {
                            "size": event.info.size,
                            "mimetype": event.info.mimetype,
                            "width": getattr(event.info, "w", None),
                            "height": getattr(event.info, "h", None),
                            "duration": getattr(event.info, "duration", None),
                        }
                    )

            # Extract caption if available
            if hasattr(event, "body") and event.body and event.body != media_info["filename"]:
                media_info["caption"] = event.body

            return media_info

        except Exception as e:
            logger.debug("Error extracting media info: {}", e)
            return None

    async def _on_invite(self, room: MatrixRoom, event: InviteMemberEvent) -> None:
        """Handle room invitations - auto-join when invited."""
        if not self._running or not self._client:
            return

        # Only handle invites for our bot user
        if event.state_key != self._bot_user_id:
            return

        if event.membership == "invite":
            try:
                logger.info(
                    "Auto-joining Matrix room: {} ({})",
                    room.display_name or room.room_id,
                    event.sender,
                )
                response = await self._client.join(room.room_id)
                if hasattr(response, "room_id"):
                    logger.info("Successfully joined room: {}", response.room_id)
                else:
                    logger.warning("Failed to join room: {}", response)
            except Exception as e:
                logger.error("Error joining Matrix room {}: {}", room.room_id, e)

    def _should_respond_in_room(self, room: MatrixRoom, event: RoomMessageText) -> bool:
        """Check if the bot should respond in this room based on policy."""
        # Check room allowlist if configured
        if self.config.allowRooms:
            if room.room_id not in self.config.allowRooms:
                return False

        # For direct messages (2 members = bot + user)
        if room.member_count == 2:
            if self.config.roomPolicy == "dm":
                return True
            elif self.config.roomPolicy in ["mention", "open"]:
                return True  # DMs are always allowed unless policy is restrictive
            else:
                return False

        # For group rooms
        if self.config.roomPolicy == "open":
            return True
        elif self.config.roomPolicy == "mention":
            # Check if bot is mentioned
            return self._is_bot_mentioned(event.body)
        elif self.config.roomPolicy == "dm":
            return False  # Only DMs allowed

        return False

    def _is_bot_mentioned(self, content: str) -> bool:
        """Check if the bot is mentioned in the message content."""
        if not self._bot_user_id:
            return False

        # Matrix mentions use the format @username:domain or display name
        user_localpart = self._bot_user_id.split(":")[0][1:]  # Remove @ prefix

        # Check for various mention patterns
        mention_patterns = [
            rf"@{re.escape(self._bot_user_id)}",  # Full user ID
            rf"@{re.escape(user_localpart)}",  # Just username part
            rf"\b{re.escape(user_localpart)}\b",  # Username as word
        ]

        content_lower = content.lower()
        for pattern in mention_patterns:
            if re.search(pattern, content_lower, re.IGNORECASE):
                return True

        return False

    def _strip_bot_mention(self, content: str) -> str:
        """Remove bot mentions from message content."""
        if not self._bot_user_id:
            return content

        user_localpart = self._bot_user_id.split(":")[0][1:]  # Remove @ prefix

        # Remove various mention patterns
        patterns = [
            rf"@{re.escape(self._bot_user_id)}\s*",
            rf"@{re.escape(user_localpart)}\s*",
        ]

        result = content
        for pattern in patterns:
            result = re.sub(pattern, "", result, flags=re.IGNORECASE)

        return result.strip()

    def _load_sync_token(self) -> str | None:
        """Load the last sync token from file."""
        try:
            if self._sync_token_file.exists():
                return self._sync_token_file.read_text().strip()
        except Exception as e:
            logger.debug("Failed to load sync token: {}", e)
        return None

    def _save_sync_token(self, token: str) -> None:
        """Save the sync token to file."""
        try:
            self._sync_token_file.parent.mkdir(parents=True, exist_ok=True)
            self._sync_token_file.write_text(token)
        except Exception as e:
            logger.debug("Failed to save sync token: {}", e)

    def is_allowed(self, sender_id: str) -> bool:
        """Check if a sender is allowed to use this bot."""
        # Use the configured allowFrom list
        allow_list = self.config.allowFrom

        # If no allow list, allow everyone
        if not allow_list:
            return True

        # Direct match
        if sender_id in allow_list:
            return True

        # For Matrix, also check just the username part (without domain)
        if ":" in sender_id:
            username = sender_id.split(":")[0]
            if username in allow_list or username[1:] in allow_list:  # With/without @
                return True

        return False

    @staticmethod
    def _split_message(content: str, max_len: int = 65000) -> list[str]:
        """Split content into chunks within max_len, preferring line breaks."""
        if len(content) <= max_len:
            return [content]

        chunks: list[str] = []
        while content:
            if len(content) <= max_len:
                chunks.append(content)
                break

            # Find best cut point
            cut = content[:max_len]
            pos = cut.rfind("\n")
            if pos == -1:
                pos = cut.rfind(" ")
            if pos == -1:
                pos = max_len

            chunks.append(content[:pos])
            content = content[pos:].lstrip()

        return chunks

    @staticmethod
    def _markdown_to_matrix_html(text: str) -> str:
        """Convert basic Markdown to Matrix HTML format."""
        if not text:
            return ""

        # Simple conversions for common Markdown patterns
        html = text

        # Code blocks ```code``` -> <pre><code>code</code></pre>
        html = re.sub(r"```(.*?)```", r"<pre><code>\1</code></pre>", html, flags=re.DOTALL)

        # Inline code `code` -> <code>code</code>
        html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

        # Bold **text** or __text__ -> <strong>text</strong>
        html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
        html = re.sub(r"__(.+?)__", r"<strong>\1</strong>", html)

        # Italic *text* or _text_ -> <em>text</em>
        html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)
        html = re.sub(r"\b_(.+?)_\b", r"<em>\1</em>", html)

        # Strikethrough ~~text~~ -> <del>text</del>
        html = re.sub(r"~~(.+?)~~", r"<del>\1</del>", html)

        # Links [text](url) -> <a href="url">text</a>
        html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

        # Headers # Title -> <h1>Title</h1> (simplified)
        html = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html, flags=re.MULTILINE)
        html = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html, flags=re.MULTILINE)
        html = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

        # Line breaks
        html = html.replace("\n", "<br/>")

        return html

    @staticmethod
    def _guess_mime_type(extension: str) -> str:
        """Guess MIME type from file extension."""
        extension = extension.lower()
        mime_map = {
            ".txt": "text/plain",
            ".md": "text/markdown",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp3": "audio/mpeg",
            ".ogg": "audio/ogg",
            ".wav": "audio/wav",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".pdf": "application/pdf",
            ".json": "application/json",
        }
        return mime_map.get(extension, "application/octet-stream")

    def _extract_thread_info(self, event: RoomMessageText) -> dict | None:
        """Extract thread information from Matrix events."""
        try:
            if hasattr(event, "unsigned") and event.unsigned:
                relations = event.unsigned.get("relations", {})
                if relations and isinstance(relations, dict):
                    # Check if this is part of a thread
                    if "m.thread" in relations:
                        thread_info = relations["m.thread"]
                        return {
                            "in_reply_to": thread_info.get("in_reply_to"),
                            "is_falling_back": thread_info.get("is_falling_back", False),
                            "event_id": thread_info.get("event_id"),
                        }

                    # Check if this event references another event (reply)
                    if "m.replace" in relations:
                        return {
                            "in_reply_to": relations["m.replace"].get("event_id"),
                            "is_falling_back": True,
                        }

            return None
        except Exception as e:
            logger.debug("Error extracting thread info: {}", e)
            return None

    async def _send_message_with_thread_relation(
        self, room_id: str, content: str, thread_info: dict | None = None
    ) -> None:
        """Send message with thread relation if thread_info is provided."""
        message_content = {"msgtype": "m.text", "body": content}

        if thread_info and thread_info.get("in_reply_to"):
            # Add thread relation
            message_content["m.relates_to"] = {
                "m.rel_type": "m.thread",
                "m.in_reply_to": {
                    "event_id": thread_info["in_reply_to"],
                },
                "is_falling_back": thread_info.get("is_falling_back", True),
            }

        response = await self._client.room_send(
            room_id=room_id, message_type="m.room.message", content=message_content
        )

        if hasattr(response, "event_id"):
            logger.debug("Matrix message sent with thread relation: {}", response.event_id)
        else:
            logger.warning("Matrix send failed: {}", response)
