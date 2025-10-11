from sqlalchemy import Column, Integer, String, Float, DateTime, Enum as SQLEnum, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from database.database import Base

# ========================== 
# ENUM типы
# ==========================

class GameStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"  # Добавлено для устранения ошибки

class GameResult(enum.Enum):
    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"

class TransactionStatus(enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"

# ========================== 
# МОДЕЛИ
# ==========================

class User(Base):
    """Модель пользователя"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255))
    first_name = Column(String(255))
    
    # Статистика
    total_wagered = Column(Float, default=0.0)
    total_won = Column(Float, default=0.0)
    games_played = Column(Integer, default=0)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    games = relationship("Game", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"

class Game(Base):
    """Модель игры"""
    __tablename__ = "games"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Данные игры
    game_type = Column(String(50), nullable=False)
    bet_amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USDT")
    
    # Статус и результат
    status = Column(SQLEnum(GameStatus), default=GameStatus.PENDING)  # Использует обновлённый enum
    result = Column(SQLEnum(GameResult), nullable=True)
    payout = Column(Float, default=0.0)
    
    # Дополнительные данные (JSON строка)
    game_data = Column(Text, nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="games")
    transaction = relationship("Transaction", back_populates="game", uselist=False)
    
    def __repr__(self):
        return f"<Game(id={self.id}, game_id={self.game_id}, type={self.game_type}, status={self.status})>"

class Transaction(Base):
    """Модель транзакции"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String(255), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True)
    
    # Данные транзакции
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USDT")
    status = Column(SQLEnum(TransactionStatus), default=TransactionStatus.PENDING)
    
    # URL для оплаты
    pay_url = Column(String(500), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    
    # Связи
    user = relationship("User", back_populates="transactions")
    game = relationship("Game", back_populates="transaction")
    
    def __repr__(self):
        return f"<Transaction(id={self.id}, invoice_id={self.invoice_id}, status={self.status})>"