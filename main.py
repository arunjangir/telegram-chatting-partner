import asyncio
import json
import os
import time
import random
import glob
from datetime import datetime
from typing import Dict, List, Optional
import boto3
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import UpdateUserTyping, UpdateChatUserTyping, MessageMediaPhoto, MessageMediaDocument

# Configuration
API_ID = 22822226
API_HASH = 'd05b6dbac2ffba48e324lsd93346'
SESSION_STR = "1BVtsOI8BuygwmpxxxxxxxxxxxxxxxxxxxxhMkKl2EoJBmwU6axuOc3ZKS-zJXPap8UDaConT44MWX9NWH_qp-dL6jLtFNyuRH9XvBb7f-Bp4D5W03_DZw07LS62rYPnE17WRg9ZYKR0wWouMl6gk9pLQQkNrSimOK3z4NTmmkm0gw5AkV_77XlDYWXhh5IMu3aWplbrPY4jmIYVUzXVtmsG10GTMc-Db8o024CytWLkd6JG5yZrFLxtu4I8Hd2OPilT5bSiBEjbVeCnWimbWW5QfK7dkNkeyuxKMkMV45Ag8pN_Fzupo="

# Global variables
user_typing_timestamps = {}  # Track when user last typed
user_message_queue = {}  # Queue messages while user is typing
user_typing_status = {}
conversation_contexts = {}
user_photo_history = {}  # Track sent photos per user with full details
user_video_history = {}  # Track sent videos per user with full details

# AWS Bedrock Configuration
AWS_ACCESS_KEY = "AKIxxxxxxxxxxxxxxxxxxxxxxxxxUW"
AWS_SECRET_KEY = "PN/PxCymmaKxxxxxxxxxxxxxxxxxSBkWhVq45SRfLH"
AWS_REGION = "us-east-1"

# ElevenLabs Configuration
ELEVENLABS_API_KEY = "sk_28003479xxxxxxxxxxxxxxxxxxxxxxxxxxxxxa3792edf"
ELEVENLABS_VOICE_ID = "Bjt2xxxxxxxxxxxxxxxxxxxxxH0bpLU"  # Default voice ID

class TelegramBedrocBot:
    def __init__(self):
        self.client = None
        self.bedrock_client = None
        self.setup_aws_client()
        print("🚀 Initializing Telegram Bedrock Bot...")
        
    def setup_aws_client(self):
        """Initialize AWS Bedrock client"""
        try:
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                aws_access_key_id=AWS_ACCESS_KEY,
                aws_secret_access_key=AWS_SECRET_KEY,
                region_name=AWS_REGION
            )
            print("✅ AWS Bedrock client initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize AWS Bedrock client: {e}")

    async def create_session(self):
        """Create Telegram session with fallback to new login"""
        try:
            print("🔐 Attempting to connect with existing session...")
            self.client = TelegramClient(StringSession(SESSION_STR), API_ID, API_HASH)
            await self.client.start()
            print("✅ Connected with existing session")
            return True
        except Exception as e:
            print(f"❌ Existing session failed: {e}")
            print("🔐 Creating new session...")
            return await self.create_new_session()

    async def create_new_session(self):
        """Create new session if existing one fails"""
        try:
            self.client = TelegramClient(StringSession(), API_ID, API_HASH)
            await self.client.start()
            new_session = self.client.session.save()
            print("✅ New session created successfully!")
            print(f"🔑 Save this session string: {new_session}")
            
            # Save to file for future use
            with open('new_session.txt', 'w') as f:
                f.write(new_session)
            print("💾 Session saved to 'new_session.txt'")
            return True
        except Exception as e:
            print(f"❌ Failed to create new session: {e}")
            return False

    def is_new_user(self, user_id: str) -> bool:
        """Check if user is new by checking if conversation file exists"""
        filename = f"conversations/user_{user_id}.json"
        file_exists = os.path.exists(filename)
        
        if file_exists:
            print(f"👤 User {user_id} is existing user (JSON file found)")
            return False
        else:
            print(f"🆕 User {user_id} is new user (no JSON file)")
            return True

    def has_intro_in_conversation(self, user_id: str) -> bool:
        """Check if intro message is already in conversation history"""
        try:
            conversation = self.load_conversation(user_id)
            intro_text = "this is my voice"
            
            for msg in conversation:
                if msg.get('role') == 'CHATBOT' and intro_text in msg.get('message', ''):
                    print(f"✅ Intro already exists in conversation for user {user_id}")
                    return True
            
            print(f"❌ No intro found in conversation for user {user_id}")
            return False
        except Exception as e:
            print(f"❌ Error checking intro in conversation: {e}")
            return False

    def clean_conversation_history(self, conversation: List[Dict]) -> List[Dict]:
        """Clean conversation history for Bedrock API"""
        cleaned = []
        for msg in conversation:
            # Only include role and message, remove any tool_calls or other fields
            if 'role' in msg and 'message' in msg and msg['message'].strip():
                cleaned.append({
                    "role": msg['role'],
                    "message": msg['message']
                })
        return cleaned

    def load_conversation(self, user_id: str) -> List[Dict]:
        """Load conversation history for a user"""
        filename = f"conversations/user_{user_id}.json"
        try:
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Clean loaded data
                    cleaned_data = []
                    for msg in data:
                        if isinstance(msg, dict) and 'role' in msg and 'message' in msg:
                            cleaned_data.append({
                                'role': msg['role'],
                                'message': msg['message']
                            })
                    print(f"📚 Loaded {len(cleaned_data)} messages for user {user_id}")
                    return cleaned_data
        except Exception as e:
            print(f"❌ Error loading conversation for user {user_id}: {e}")
        return []

    def save_conversation(self, user_id: str, conversation: List[Dict]):
        """Save conversation history for a user"""
        os.makedirs("conversations", exist_ok=True)
        filename = f"conversations/user_{user_id}.json"
        try:
            # Clean conversation before saving
            cleaned_conversation = []
            for msg in conversation:
                if isinstance(msg, dict) and 'role' in msg and 'message' in msg:
                    cleaned_conversation.append({
                        'role': msg['role'],
                        'message': msg['message']
                    })
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(cleaned_conversation, f, ensure_ascii=False, indent=2)
            print(f"💾 Saved conversation for user {user_id} ({len(cleaned_conversation)} messages)")
        except Exception as e:
            print(f"❌ Error saving conversation for user {user_id}: {e}")

    def truncate_conversation(self, conversation: List[Dict], max_tokens: int = 4000) -> List[Dict]:
        """Truncate conversation to fit within token limit"""
        if not conversation:
            return []
        
        # Rough estimation: 1 token ≈ 4 characters
        total_chars = sum(len(msg.get('message', '')) for msg in conversation)
        
        if total_chars > max_tokens * 4:
            # Keep recent messages and first few messages for context
            recent_count = min(8, len(conversation))  # Last 8 messages
            context_count = min(2, len(conversation))  # First 2 messages
            
            if len(conversation) > recent_count + context_count:
                context_messages = conversation[:context_count]
                recent_messages = conversation[-recent_count:]
                
                truncated = context_messages + [{"role": "CHATBOT", "message": "[पिछली बातचीत छोटी की गई...]"}] + recent_messages
                print(f"✂️ Truncated conversation from {len(conversation)} to {len(truncated)} messages")
                return truncated
        
        return conversation

    async def send_intro_messages(self, chat_id: str):
        """Send intro voice messages to new users"""
        try:
            print(f"🎤 Sending intro messages to user {chat_id}")
            
            # First send intro.mp3 as voice note (with graph)
            if os.path.exists("intro.mp3"):
                await self.client.send_file(
                    int(chat_id),
                    "intro.mp3",
                    voice_note=True
                )
                print(f"🎤 Sent intro.mp3 as voice note to user {chat_id}")
            
            # Small delay between messages
            await asyncio.sleep(2)
            
            # Then send sample.mp3 as regular audio (without graph)
            if os.path.exists("sample.mp3"):
                await self.client.send_file(
                    int(chat_id),
                    "sample.mp3",
                    voice_note=False  # This makes it show as regular audio without graph
                )
                print(f"🎵 Sent sample.mp3 as regular audio to user {chat_id}")
            
            # Save the intro message text to conversation history
            intro_text = "Hi, ye meri aawaz h"
            
            # Load existing conversation and add intro message
            conversation = self.load_conversation(chat_id)
            conversation.append({
                "role": "CHATBOT",
                "message": intro_text
            })
            self.save_conversation(chat_id, conversation)
            print(f"💾 Saved intro message to conversation for user {chat_id}")
            
        except Exception as e:
            print(f"❌ Error sending intro messages to user {chat_id}: {e}")

    async def show_typing_action(self, chat_id: str, action_type: str = "typing"):
        """Show typing or recording action"""
        try:
            from telethon.tl.functions.messages import SetTypingRequest
            from telethon.tl.types import SendMessageTypingAction, SendMessageRecordAudioAction
            
            if action_type == "recording":
                action = SendMessageRecordAudioAction()
                print(f"🎤 Showing 'recording...' for user {chat_id}")
            else:
                action = SendMessageTypingAction()
                print(f"⌨️ Showing 'typing...' for user {chat_id}")
            
            await self.client(SetTypingRequest(
                peer=int(chat_id),
                action=action
            ))
            
        except Exception as e:
            print(f"❌ Error showing typing action: {e}")

    # [Rest of your tool functions remain the same - send_photo_tool, send_video_tool, etc.]
    async def send_photo_tool(self, chat_id: str, photo_type: str = "normal", photo_number: str = None, specific_photo: str = None) -> str:
        """Tool to send photos dynamically with random filename support"""
        try:
            # Initialize user history if not exists
            if chat_id not in user_photo_history:
                user_photo_history[chat_id] = {
                    'normal': [],
                    'home': [],
                    'sent_order': []  # Track order of sent photos
                }
            
            if specific_photo:
                # Handle requests like "pichle do photos" or specific photo requests
                if specific_photo.lower() in ['pichle', 'previous', 'last', 'wo']:
                    # Send the last photo sent
                    if user_photo_history[chat_id]['sent_order']:
                        last_photo = user_photo_history[chat_id]['sent_order'][-1]
                        photo_path = last_photo['path']
                        
                        if os.path.exists(photo_path):
                            await self.client.send_file(
                                int(chat_id), 
                                photo_path,
                                ttl=3
                            )
                            print(f"📸 Re-sent previous photo to user {chat_id}: {os.path.basename(photo_path)}")
                            return f"previous_photo_sent"
                        else:
                            return "Previous photo not found"
                    else:
                        return "No previous photos to show"
                
                elif specific_photo.lower() in ['pichle do', 'last two', 'previous two']:
                    # Send last two photos
                    if len(user_photo_history[chat_id]['sent_order']) >= 2:
                        last_two = user_photo_history[chat_id]['sent_order'][-2:]
                        for photo_info in last_two:
                            if os.path.exists(photo_info['path']):
                                await self.client.send_file(
                                    int(chat_id), 
                                    photo_info['path'],
                                    ttl=3
                                )
                                await asyncio.sleep(1)  # Small delay between photos
                        print(f"📸 Re-sent last two photos to user {chat_id}")
                        return f"last_two_photos_sent"
                    else:
                        return "Not enough previous photos to show"
                
                else:
                    # Try to find specific photo by partial name match
                    all_photos = []
                    if photo_type == "normal":
                        all_photos = glob.glob('photos/*')
                    else:
                        all_photos = glob.glob('photos/*')
                    
                    # Filter for image files
                    all_photos = [p for p in all_photos if p.lower().endswith(('.jpg', '.jpeg', '.png'))]
                    
                    # Find photo with matching name
                    matching_photos = [p for p in all_photos if specific_photo.lower() in os.path.basename(p).lower()]
                    
                    if matching_photos:
                        photo_path = matching_photos[0]
                    else:
                        return f"Photo '{specific_photo}' not found"
            else:
                # Get available photos based on type
                if photo_type == "normal":
                    available_photos = glob.glob('photos/*')
                else:
                    available_photos = glob.glob('photos/*')
                
                # Filter for image files only
                available_photos = [p for p in available_photos if p.lower().endswith(('.jpg', '.jpeg', '.png'))]
                
                if not available_photos:
                    return f"No {photo_type} photos available"
                
                # Get unsent photos first
                sent_photos = [item['filename'] for item in user_photo_history[chat_id][photo_type]]
                unsent_photos = [p for p in available_photos if os.path.basename(p) not in sent_photos]
                
                # If all photos sent, choose from all available
                if not unsent_photos:
                    unsent_photos = available_photos
                    user_photo_history[chat_id][photo_type] = []  # Reset history
                    user_photo_history[chat_id]['sent_order'] = []  # Reset order tracking
                
                # Choose random photo
                photo_path = random.choice(unsent_photos)
            
            # Send the photo
            if os.path.exists(photo_path):
                await self.client.send_file(
                    int(chat_id), 
                    photo_path,
                    ttl=3
                )
                
                # Update history with full details
                photo_info = {
                    'filename': os.path.basename(photo_path),
                    'path': photo_path,
                    'sent_time': datetime.now().isoformat(),
                    'type': photo_type
                }
                
                # Add to type-specific history
                user_photo_history[chat_id][photo_type].append(photo_info)
                
                # Add to sent order (keep last 10 for memory)
                user_photo_history[chat_id]['sent_order'].append(photo_info)
                if len(user_photo_history[chat_id]['sent_order']) > 10:
                    user_photo_history[chat_id]['sent_order'] = user_photo_history[chat_id]['sent_order'][-10:]
                
                print(f"📸 Sent {photo_type} photo to user {chat_id}: {os.path.basename(photo_path)}")
                return f"photo_sent"
            else:
                print(f"❌ Photo not found: {photo_path}")
                return f"Photo not found"
                
        except Exception as e:
            print(f"❌ Error sending photo: {e}")
            return f"Failed to send photo: {str(e)}"

    async def send_video_tool(self, chat_id: str, video_type: str = "normal", video_number: str = None, specific_video: str = None) -> str:
        """Tool to send videos dynamically with random filename support"""
        try:
            # Initialize user history if not exists
            if chat_id not in user_video_history:
                user_video_history[chat_id] = {
                    'normal': [],
                    'nude': [],
                    'sent_order': []  # Track order of sent videos
                }
            
            if specific_video:
                # Handle requests like "pichla video", "wo video"
                if specific_video.lower() in ['pichla', 'previous', 'last', 'wo']:
                    # Send the last video sent
                    if user_video_history[chat_id]['sent_order']:
                        last_video = user_video_history[chat_id]['sent_order'][-1]
                        video_path = last_video['path']
                        
                        if os.path.exists(video_path):
                            await self.client.send_file(
                                int(chat_id), 
                                video_path,
                                ttl=1
                            )
                            print(f"🎥 Re-sent previous video to user {chat_id}: {os.path.basename(video_path)}")
                            return f"previous_video_sent"
                        else:
                            return "Previous video not found"
                    else:
                        return "No previous videos to show"
                
                else:
                    # Try to find specific video by partial name match
                    all_videos = glob.glob('videos/*')
                    # Filter for video files
                    all_videos = [v for v in all_videos if v.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
                    
                    # Find video with matching name
                    matching_videos = [v for v in all_videos if specific_video.lower() in os.path.basename(v).lower()]
                    
                    if matching_videos:
                        video_path = matching_videos[0]
                    else:
                        return f"Video '{specific_video}' not found"
            else:
                # Get available videos
                available_videos = glob.glob('videos/*')
                # Filter for video files only
                available_videos = [v for v in available_videos if v.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
                
                if not available_videos:
                    return f"No {video_type} videos available"
                
                # Get unsent videos first
                sent_videos = [item['filename'] for item in user_video_history[chat_id].get(video_type, [])]
                unsent_videos = [v for v in available_videos if os.path.basename(v) not in sent_videos]
                
                # If all videos sent, choose from all available
                if not unsent_videos:
                    unsent_videos = available_videos
                    user_video_history[chat_id][video_type] = []  # Reset history
                    user_video_history[chat_id]['sent_order'] = []  # Reset order tracking
                
                # Choose random video
                video_path = random.choice(unsent_videos)
            
            # Send the video
            if os.path.exists(video_path):
                await self.client.send_file(
                    int(chat_id), 
                    video_path,
                    ttl=1
                )
                
                # Update history with full details
                video_info = {
                    'filename': os.path.basename(video_path),
                    'path': video_path,
                    'sent_time': datetime.now().isoformat(),
                    'type': video_type
                }
                
                # Add to type-specific history
                if video_type not in user_video_history[chat_id]:
                    user_video_history[chat_id][video_type] = []
                user_video_history[chat_id][video_type].append(video_info)
                
                # Add to sent order (keep last 10 for memory)
                user_video_history[chat_id]['sent_order'].append(video_info)
                if len(user_video_history[chat_id]['sent_order']) > 10:
                    user_video_history[chat_id]['sent_order'] = user_video_history[chat_id]['sent_order'][-10:]
                
                print(f"🎥 Sent {video_type} video to user {chat_id}: {os.path.basename(video_path)}")
                return f"video_sent"
            else:
                print(f"❌ Video not found: {video_path}")
                return f"Video not found"
                
        except Exception as e:
            print(f"❌ Error sending video: {e}")
            return f"Failed to send video: {str(e)}"

    async def send_home_photo_tool(self, chat_id: str, specific_photo: str = None) -> str:
        """Tool to send Shruti's home photos from hphotos directory with random filename support"""
        try:
            # Initialize user history if not exists
            if chat_id not in user_photo_history:
                user_photo_history[chat_id] = {
                    'normal': [],
                    'home': [],
                    'shruti_home': [],
                    'sent_order': []
                }
            
            if 'shruti_home' not in user_photo_history[chat_id]:
                user_photo_history[chat_id]['shruti_home'] = []
            
            if specific_photo:
                # Handle requests like "pichla home photo", "wo ghar wali photo"
                if specific_photo.lower() in ['pichla', 'previous', 'last', 'wo', 'ghar wali']:
                    # Find last home photo sent
                    home_photos_sent = [item for item in user_photo_history[chat_id]['sent_order'] 
                                      if 'hphotos' in item['path']]
                    
                    if home_photos_sent:
                        last_home_photo = home_photos_sent[-1]
                        photo_path = last_home_photo['path']
                        
                        if os.path.exists(photo_path):
                            await self.client.send_file(
                                int(chat_id), 
                                photo_path,
                                ttl=3
                            )
                            print(f"🏠 Re-sent previous home photo to user {chat_id}: {os.path.basename(photo_path)}")
                            return f"previous_home_photo_sent"
                        else:
                            return "Previous home photo not found"
                    else:
                        return "No previous home photos to show"
                
                else:
                    # Try to find specific photo by name
                    photo_path = f'hphotos/{specific_photo}'
                    if not photo_path.endswith(('.jpg', '.jpeg', '.png')):
                        # Try different extensions
                        for ext in ['.jpg', '.jpeg', '.png']:
                            test_path = f'hphotos/{specific_photo}{ext}'
                            if os.path.exists(test_path):
                                photo_path = test_path
                                break
                        else:
                            # Try partial name matching
                            available_photos = glob.glob('hphotos/*')
                            available_photos = [p for p in available_photos if p.lower().endswith(('.jpg', '.jpeg', '.png'))]
                            matching_photos = [p for p in available_photos if specific_photo.lower() in os.path.basename(p).lower()]
                            
                            if matching_photos:
                                photo_path = matching_photos[0]
                            else:
                                return f"Home photo '{specific_photo}' not found"
            else:
                # Get available home photos
                available_photos = glob.glob('hphotos/*')
                available_photos = [p for p in available_photos if p.lower().endswith(('.jpg', '.jpeg', '.png'))]
                
                if not available_photos:
                    return "No home photos of Shruti available"
                
                # Get unsent photos first
                sent_photos = [item['filename'] for item in user_photo_history[chat_id]['shruti_home']]
                unsent_photos = [p for p in available_photos if os.path.basename(p) not in sent_photos]
                
                # If all photos sent, choose from all available
                if not unsent_photos:
                    unsent_photos = available_photos
                    user_photo_history[chat_id]['shruti_home'] = []  # Reset history
                
                # Choose random photo
                photo_path = random.choice(unsent_photos)
            
            # Send the photo
            if os.path.exists(photo_path):
                await self.client.send_file(
                    int(chat_id), 
                    photo_path,
                    ttl=3
                )
                
                # Update history with full details
                photo_info = {
                    'filename': os.path.basename(photo_path),
                    'path': photo_path,
                    'sent_time': datetime.now().isoformat(),
                    'type': 'shruti_home'
                }
                
                # Add to home photo history
                user_photo_history[chat_id]['shruti_home'].append(photo_info)
                
                # Add to sent order (keep last 10 for memory)
                user_photo_history[chat_id]['sent_order'].append(photo_info)
                if len(user_photo_history[chat_id]['sent_order']) > 10:
                    user_photo_history[chat_id]['sent_order'] = user_photo_history[chat_id]['sent_order'][-10:]
                
                print(f"🏠 Sent Shruti's home photo to user {chat_id}: {os.path.basename(photo_path)}")
                return f"home_photo_sent"
            else:
                print(f"❌ Home photo not found: {photo_path}")
                return f"Home photo not found"
                
        except Exception as e:
            print(f"❌ Error sending home photo: {e}")
            return f"Failed to send home photo: {str(e)}"



    async def block_user_tool(self, chat_id: str, reason: str = "inappropriate behavior") -> str:
        """Tool to block and ban user from Telegram"""
        try:
            from telethon.tl.functions.contacts import BlockRequest
            
            # Get user entity
            user_entity = await self.client.get_entity(int(chat_id))
            
            # Block the user using the proper Telethon method
            await self.client(BlockRequest(id=user_entity))
            
            print(f"🚫 Blocked user {chat_id} for: {reason}")
            return f"user_blocked"
        except Exception as e:
            print(f"❌ Error blocking user {chat_id}: {e}")
            return f"Failed to block user: {str(e)}"


    async def generate_voice_message(self, text: str, chat_id: str) -> str:
        """Generate voice message using ElevenLabs API"""
        try:
            print(f"🎤 Generating voice message for user {chat_id}")
            
            # Show recording action
            await self.show_typing_action(chat_id, "recording")
            
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            
            data = {
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.5,
                    "speed": 0.95
                }
            }
            
            response = requests.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                # Save audio file
                os.makedirs("voice_messages", exist_ok=True)
                audio_path = f"voice_messages/voice_{chat_id}_{int(time.time())}.mp3"
                
                with open(audio_path, 'wb') as f:
                    f.write(response.content)
                
                # Send voice message to Telegram with graph (voice_note=True)
                await self.client.send_file(
                    int(chat_id),
                    audio_path,
                    voice_note=True  # This shows the graph
                )
                
                # Clean up file
                os.remove(audio_path)
                print(f"🎤 Voice message sent successfully to user {chat_id}")
                return "voice_message_sent"
            else:
                print(f"❌ ElevenLabs API error: {response.status_code} - {response.text}")
                return f"Failed to generate voice: {response.status_code}"
                
        except Exception as e:
            print(f"❌ Error generating voice message: {e}")
            return f"Error generating voice: {str(e)}"

    def get_bedrock_tools(self) -> List[Dict]:
        """Define tools for Cohere model with updated descriptions"""
        return [
            {
                "name": "send_photo",
                "description": "Send a photo to the user dynamically. Works with any photo filenames. Can send previous photos when user asks 'pichle photos', 'wo photos', etc. Available types: normal",
                "parameter_definitions": {
                    "photo_type": {
                        "description": "Type of photo: 'normal'",
                        "type": "str",
                        "required": False
                    },
                    "specific_photo": {
                        "description": "Specific photo name, or 'pichle'/'previous'/'last'/'wo' for previous photos, 'pichle do' for last two photos",
                        "type": "str", 
                        "required": False
                    }
                }
            },
            {
                "name": "block_user",
                "description": "Block and delete user when user starts fighting or arguing",
                "parameter_definitions": {
                    "reason": {
                        "description": "Reason for blocking the user",
                        "type": "str",
                        "required": False
                    }
                }
            },
            {
                "name": "send_voice_message",
                "description": "only processes Hindi text in Devanagari script. Example 'मेरा नाम श्रुति है' ",
                "parameter_definitions": {
                    "text": {
                        "description": "Hindi text in Devanagari script to convert to speech",
                        "type": "str",
                        "required": True
                    }
                }
            }
        ]

    async def execute_tool(self, tool_call: Dict, chat_id: str) -> str:
        """Execute tool based on tool call"""
        tool_name = tool_call['name']
        # Coerce None to empty dict so parameters.get(...) is always safe
        parameters = tool_call.get('parameters') or {}

        print(f"🔧 Executing tool: {tool_name} with parameters: {parameters}")

        try:
            if tool_name == "send_photo":
                return await self.send_photo_tool(
                    chat_id, 
                    parameters.get('photo_type', 'normal'), 
                    parameters.get('photo_number'), 
                    parameters.get('specific_photo')
                )
            elif tool_name == "send_video":
                return await self.send_video_tool(
                    chat_id, 
                    parameters.get('video_type', 'normal'), 
                    parameters.get('video_number'), 
                    parameters.get('specific_video')
                )
            elif tool_name == "block_user":
                return await self.block_user_tool(
                    chat_id,
                    parameters.get('reason', 'inappropriate behavior')
                )
            elif tool_name == "send_voice_message":
                return await self.generate_voice_message(
                    parameters.get('text', ''),
                    chat_id
                )
            else:
                print(f"❌ Unknown tool: {tool_name}")
                return f"Unknown tool: {tool_name}"
        except Exception as e:
            print(f"❌ Error executing tool {tool_name}: {e}")
            return f"Error executing {tool_name}: {str(e)}"

    async def call_bedrock_cohere(self, message: str, chat_history: List[Dict], user_id: str) -> tuple:
        """Call AWS Bedrock Cohere model"""
        try:
            print(f"🧠 Calling Bedrock Cohere for user {user_id}")
            
            # Clean the conversation history
            cleaned_history = self.clean_conversation_history(chat_history)
            
            # Basic payload without optional parameters that might cause issues
            payload = {
                "message": message,
                "chat_history": cleaned_history,
                "preamble": """You are an Indian decent girl. Name Shruti, Age 20, Delhi Dwarka.
**Language Instructions:
- Mostly use hindi devnagri writing while using voice messages. Use decent language.

**Aim: [
-Be a friendly emotional suppot

**Block if user is abusive**
""",
                "max_tokens": 400,
                "temperature": 0.7,
                "tools": self.get_bedrock_tools()
            }
            
            print(f"🔍 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            response = self.bedrock_client.invoke_model(
                modelId='cohere.command-r-plus-v1:0',
                body=json.dumps(payload)
            )
            
            result = json.loads(response['body'].read())
            print(f"✅ Bedrock response received for user {user_id}")
            print(f"🔍 Response: {json.dumps(result, indent=2, ensure_ascii=False)}")
            
            # Handle tool calls
            if 'tool_calls' in result and result['tool_calls']:
                print(f"🔧 Processing {len(result['tool_calls'])} tool calls")
                
                tool_results = []
                for tool_call in result['tool_calls']:
                    print(f"🔧 Executing tool: {tool_call}")
                    tool_result = await self.execute_tool(tool_call, user_id)
                    tool_results.append({
                        "call": tool_call,
                        "outputs": [{"text": tool_result}]
                    })
                
                # Make follow-up request with tool results
                if tool_results:
                    # Create new conversation history with the tool call
                    updated_history = cleaned_history + [
                        {"role": "USER", "message": message },
                        {"role": "CHATBOT", "message": result.get('text', '')}
                    ]
                    
                    tool_payload = {
                        "message": "",
                        "chat_history": updated_history,
                        "preamble": """**Language Instructions:
Use casual Hindi Devanagari script like 'पहले पेमेंट करें फिर वॉयस चैट करेंगे'**""",
                        "max_tokens": 200,
                        "temperature": 0.5,
                        "tool_results": tool_results
                    }
                    
                    try:
                        print(f"🔧 Sending tool results back to Bedrock")
                        response = self.bedrock_client.invoke_model(
                            modelId='cohere.command-r-plus-v1:0',
                            body=json.dumps(tool_payload)
                        )
                        final_result = json.loads(response['body'].read())
                        final_text = final_result.get('text', '').strip()
                        
                        print(f"🔧 Tool follow-up response: {final_text}")
                        
                        # Check if we should send text response or just acknowledge tool execution
                        if any('_sent' in str(result) for result in tool_results):
                            # If blocking user, don't send any response
                            if any('user_blocked' in str(result) for result in tool_results):
                                return "", True  # Block executed successfully, no text needed
                            return "", True  # Tool executed successfully, no text needed
                        
                        return final_text, True
                        
                    except Exception as tool_error:
                        print(f"❌ Tool result processing error: {tool_error}")
                        return "", True  # Tool was executed, don't send error to user
            
            # No tool calls, return direct response
            response_text = result.get('text', 'Kya')
            print(f"💬 Direct response: {response_text}")
            return response_text, True
            
        except Exception as e:
            print(f"❌ Bedrock API error for user {user_id}: {e}")
            import traceback
            print(f"❌ Full traceback: {traceback.format_exc()}")
            return "Baad me baat krna", False

    async def handle_self_destruct_media(self, event):
        """Handle self-destruct images/media from user"""
        try:
            if event.media and hasattr(event.media, 'ttl_seconds') and event.media.ttl_seconds:
                print(f"📱 Received self-destruct media from user {event.sender_id}")
                
                # Download and open the media silently
                if isinstance(event.media, (MessageMediaPhoto, MessageMediaDocument)):
                    # Just acknowledge that we received it - no response needed
                    print(f"👁️ Opened self-destruct media from user {event.sender_id}")
                    return True
        except Exception as e:
            print(f"❌ Error handling self-destruct media: {e}")
        return False

    async def wait_for_typing_to_stop(self, chat_id: int, timeout: int = 2):
        """Wait for user to stop typing with 2 second timeout"""
        print(f"⌨️ Waiting for user {chat_id} to stop typing...")
        
        start_time = time.time()
        while True:
            current_time = time.time()
            last_typing_time = user_typing_timestamps.get(chat_id, 0)
            
            # Check if 2 seconds have passed since last typing activity
            if current_time - last_typing_time >= timeout:
                print(f"✅ User {chat_id} stopped typing, proceeding with response")
                break
            
            # Total timeout of 10 seconds maximum
            if current_time - start_time > 10:
                print(f"⏰ Maximum wait time reached for user {chat_id}")
                break
            
            # Wait a bit before checking again
            await asyncio.sleep(0.5)

    def setup_event_handlers(self):
        """Setup Telegram event handlers"""
        
        @self.client.on(events.Raw(UpdateUserTyping))
        async def handle_user_typing(event):
            user_id = event.user_id
            user_typing_status[user_id] = True
            user_typing_timestamps[user_id] = time.time()  # Record timestamp
            print(f"⌨️ User {user_id} started typing")
    
        @self.client.on(events.Raw(UpdateChatUserTyping))
        async def handle_chat_user_typing(event):
            user_id = event.from_id.user_id if hasattr(event.from_id, 'user_id') else event.from_id
            user_typing_status[user_id] = True
            user_typing_timestamps[user_id] = time.time()  # Record timestamp
            print(f"⌨️ User {user_id} started typing in chat")
    
        @self.client.on(events.NewMessage(incoming=True))
        async def handle_message(event):
            try:
                user_id = str(event.sender_id)
                message_text = event.raw_text.strip()
                
                print(f"📨 Received message from user {user_id}: {message_text}")
                
                # Check if it's a self-destruct media
                if await self.handle_self_destruct_media(event):
                    return  # Don't respond to self-destruct media
                
                # Mark as read
                entity = await event.get_input_chat()
                await event.client.send_read_acknowledge(entity)
                print(f"✅ Marked message as read for user {user_id}")
                
                # Check if this is a new user using the improved method
                is_new_user = self.is_new_user(user_id)
                
                if is_new_user:
                    print(f"🆕 New user detected: {user_id}")
                    
                    # Wait 17 seconds before processing for new users
                    print(f"⏰ Waiting 17 seconds before responding to new user {user_id}")
                    await asyncio.sleep(17)
                    
                    # Send intro messages first
                    await self.send_intro_messages(user_id)
                    
                    # Don't process the user's first message with AI
                    # Just send the intro messages and return
                    return
                else:
                    # For existing users, check if intro is already in conversation
                    # This prevents duplicate intro messages if the script restarts
                    if self.has_intro_in_conversation(user_id):
                        print(f"✅ Existing user {user_id} already has intro in conversation")
                    else:
                        print(f"⚠️ Existing user {user_id} missing intro - this shouldn't happen normally")
                
                # Initialize message queue for user if not exists
                if user_id not in user_message_queue:
                    user_message_queue[user_id] = []
                
                # Add message to queue
                user_message_queue[user_id].append(message_text)
                
                # Reset typing status when message is received
                user_typing_status[int(user_id)] = False
                user_typing_timestamps[int(user_id)] = time.time()
                
                # Wait for user to stop typing (2 seconds)
                await self.wait_for_typing_to_stop(int(user_id), timeout=2)
                
                # Process all queued messages
                if user_id in user_message_queue and user_message_queue[user_id]:
                    # Combine all messages in queue
                    combined_message = " ".join(user_message_queue[user_id])
                    
                    # Clear the queue
                    user_message_queue[user_id] = []
                    
                    print(f"📝 Processing combined message from user {user_id}: {combined_message}")
                    
                    # Add random delay before responding (1-6 seconds)
                    delay = random.randint(1, 6)
                    print(f"⏰ Adding random delay of {delay} seconds before responding to user {user_id}")
                    await asyncio.sleep(delay)
                    
                    # Load conversation history
                    conversation = self.load_conversation(user_id)
                    
                    # Truncate conversation if too long
                    conversation = self.truncate_conversation(conversation)
                    
                    # Add user message to conversation
                    conversation.append({
                        "role": "USER",
                        "message": combined_message
                    })
                    
                    # Get response from Bedrock
                    response_text, success = await self.call_bedrock_cohere(
                        combined_message, 
                        conversation[:-1],  # Don't include the current message in history
                        user_id
                    )
                    
                    if success:
                        # Show typing action before sending text response
                        if response_text and response_text.strip():
                            await self.show_typing_action(user_id, "typing")
                            # Small delay to show typing
                            await asyncio.sleep(1)
                        
                        # Add bot response to conversation only if there's text
                        if response_text and response_text.strip():
                            conversation.append({
                                "role": "CHATBOT",
                                "message": response_text
                            })
                        else:
                            # For tool-only responses, add a placeholder
                            conversation.append({
                                "role": "CHATBOT", 
                                "message": "[Tool executed]"
                            })
                        
                        # Save conversation
                        self.save_conversation(user_id, conversation)
                        
                        # Send response only if there's meaningful text
                        if response_text and response_text.strip():
                            await event.respond(response_text)
                            print(f"📤 Sent response to user {user_id}")
                        else:
                            print(f"📤 Tool executed for user {user_id}, no text response sent")
                    else:
                        await event.respond("Bye")
                        print(f"❌ Failed to get response for user {user_id}")
                
            except Exception as e:
                print(f"❌ Error handling message: {e}")
                import traceback
                print(f"❌ Full traceback: {traceback.format_exc()}")
                try:
                    await event.respond("Bbye")
                except:
                    pass

    async def start_bot(self):
        """Start the bot"""
        print("🚀 Starting Telegram Bedrock Bot...")
        
        # Create session
        if not await self.create_session():
            print("❌ Failed to create session. Exiting.")
            return
        
        # Setup event handlers
        self.setup_event_handlers()
        
        print("✅ Bot is online and ready!")
        print("🔄 Bot will respond using AWS Bedrock Cohere model")
        print("📁 Conversations will be saved per user")
        print("🔧 Tools available: photos, videos, payments, voice messages, QR code, blocking")
        print("⏰ Random delays (1-6 seconds) added to responses")
        print("📱 Self-destruct media will be opened silently")
        print("🎥 Videos sent as view once")
        print("⌨️ Bot waits 2 seconds for user to stop typing before processing")
        print("🇮🇳 All responses and voice messages in Hindi Devanagari")
        print("🎤 New users get intro.mp3 (with graph) and sample.mp3 (without graph)")
        print("⏰ 17 second delay before responding to new users")
        print("🎤 Voice messages show graph and 'recording...' action")
        print("📝 Voice message text is saved to conversation history")
        print("🔇 Users are blocked silently without notification")
        print("🔍 New user detection based on JSON file existence")
        print("🚫 Prevents duplicate intro messages for existing users")
        
        # Keep the bot running
        await self.client.run_until_disconnected()

async def main():
    """Main function"""
    bot = TelegramBedrocBot()
    await bot.start_bot()

if __name__ == "__main__":
    asyncio.run(main())
