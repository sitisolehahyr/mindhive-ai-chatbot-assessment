import json
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime
from app.models.conversation import ConversationMemory, ConversationTurn, ConversationState, IntentType
import asyncio
from contextlib import asynccontextmanager


class MemoryManager:
    def __init__(self, db_path: str = "conversation_memory.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                conversation_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                context TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_turns (
                turn_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                bot_response TEXT NOT NULL,
                intent TEXT NOT NULL,
                entities TEXT,
                timestamp TIMESTAMP,
                confidence REAL,
                FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_slots (
                conversation_id TEXT NOT NULL,
                slot_name TEXT NOT NULL,
                slot_value TEXT,
                confidence REAL,
                last_updated TIMESTAMP,
                PRIMARY KEY (conversation_id, slot_name),
                FOREIGN KEY (conversation_id) REFERENCES conversations (conversation_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def create_conversation(self, user_id: str, conversation_id: str) -> ConversationMemory:
        memory = ConversationMemory(
            conversation_id=conversation_id,
            user_id=user_id,
            state=ConversationState.ACTIVE
        )
        
        await self.save_conversation(memory)
        return memory
    
    async def save_conversation(self, memory: ConversationMemory):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO conversations 
            (conversation_id, user_id, state, created_at, updated_at, context)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            memory.conversation_id,
            memory.user_id,
            memory.state.value,
            memory.created_at.isoformat(),
            memory.updated_at.isoformat(),
            json.dumps(memory.context)
        ))
        
        for turn in memory.turns:
            cursor.execute('''
                INSERT OR REPLACE INTO conversation_turns 
                (turn_id, conversation_id, user_message, bot_response, intent, entities, timestamp, confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                turn.turn_id,
                memory.conversation_id,
                turn.user_message,
                turn.bot_response,
                turn.intent.value,
                json.dumps(turn.entities),
                turn.timestamp.isoformat(),
                turn.confidence
            ))
        
        for slot_name, slot in memory.slots.items():
            cursor.execute('''
                INSERT OR REPLACE INTO conversation_slots 
                (conversation_id, slot_name, slot_value, confidence, last_updated)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                memory.conversation_id,
                slot_name,
                json.dumps(slot.value),
                slot.confidence,
                slot.last_updated.isoformat()
            ))
        
        conn.commit()
        conn.close()
    
    async def get_conversation(self, conversation_id: str) -> Optional[ConversationMemory]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT conversation_id, user_id, state, created_at, updated_at, context
            FROM conversations WHERE conversation_id = ?
        ''', (conversation_id,))
        
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        
        memory = ConversationMemory(
            conversation_id=result[0],
            user_id=result[1],
            state=ConversationState(result[2]),
            created_at=datetime.fromisoformat(result[3]),
            updated_at=datetime.fromisoformat(result[4]),
            context=json.loads(result[5]) if result[5] else {}
        )
        
        cursor.execute('''
            SELECT turn_id, user_message, bot_response, intent, entities, timestamp, confidence
            FROM conversation_turns WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,))
        
        turns = cursor.fetchall()
        for turn_data in turns:
            turn = ConversationTurn(
                turn_id=turn_data[0],
                user_message=turn_data[1],
                bot_response=turn_data[2],
                intent=IntentType(turn_data[3]),
                entities=json.loads(turn_data[4]) if turn_data[4] else {},
                timestamp=datetime.fromisoformat(turn_data[5]),
                confidence=turn_data[6]
            )
            memory.turns.append(turn)
        
        cursor.execute('''
            SELECT slot_name, slot_value, confidence, last_updated
            FROM conversation_slots WHERE conversation_id = ?
        ''', (conversation_id,))
        
        slots = cursor.fetchall()
        for slot_data in slots:
            from app.models.conversation import ConversationSlot
            slot = ConversationSlot(
                name=slot_data[0],
                value=json.loads(slot_data[1]) if slot_data[1] else None,
                confidence=slot_data[2],
                last_updated=datetime.fromisoformat(slot_data[3])
            )
            memory.slots[slot_data[0]] = slot
        
        conn.close()
        return memory
    
    async def add_turn(self, conversation_id: str, turn: ConversationTurn):
        memory = await self.get_conversation(conversation_id)
        if memory:
            memory.add_turn(turn)
            await self.save_conversation(memory)
    
    async def update_slot(self, conversation_id: str, slot_name: str, value: Any, confidence: float = 1.0):
        memory = await self.get_conversation(conversation_id)
        if memory:
            memory.update_slot(slot_name, value, confidence)
            await self.save_conversation(memory)
    
    async def get_user_conversations(self, user_id: str) -> List[ConversationMemory]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT conversation_id FROM conversations 
            WHERE user_id = ? ORDER BY updated_at DESC
        ''', (user_id,))
        
        conversation_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        conversations = []
        for conv_id in conversation_ids:
            memory = await self.get_conversation(conv_id)
            if memory:
                conversations.append(memory)
        
        return conversations
    
    async def delete_conversation(self, conversation_id: str):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM conversation_slots WHERE conversation_id = ?', (conversation_id,))
        cursor.execute('DELETE FROM conversation_turns WHERE conversation_id = ?', (conversation_id,))
        cursor.execute('DELETE FROM conversations WHERE conversation_id = ?', (conversation_id,))
        
        conn.commit()
        conn.close()
    
    async def cleanup_old_conversations(self, days_old: int = 30):
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT conversation_id FROM conversations 
            WHERE updated_at < ?
        ''', (cutoff_date.isoformat(),))
        
        old_conversations = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        for conv_id in old_conversations:
            await self.delete_conversation(conv_id)