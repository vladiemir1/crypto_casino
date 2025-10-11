from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Game, Transaction, GameStatus, GameResult, TransactionStatus
from datetime import datetime
from typing import Optional


class UserCRUD:
    @staticmethod
    async def get_or_create(session: AsyncSession, telegram_id: int, username: str = None, first_name: str = None) -> User:
        """Получить или создать пользователя по telegram_id"""
        # Ищем пользователя
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()
        
        if user is None:
            # Создаем нового пользователя
            user = User(
                telegram_id=telegram_id,
                username=username or f"user_{telegram_id}",
                first_name=first_name,
                total_wagered=0.0,
                total_won=0.0,
                games_played=0
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        
        return user
    
    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_stats(session: AsyncSession, user: User, wagered: float = 0, won: float = 0, games: int = 0):
        """Обновить статистику пользователя"""
        user.total_wagered += wagered
        user.total_won += won
        user.games_played += games
        user.last_activity = datetime.utcnow()
        await session.commit()


class GameCRUD:
    @staticmethod
    async def create(session: AsyncSession, game_id: str, user_id: int, game_type: str, 
                    bet_amount: float, currency: str) -> Game:
        """Создать новую игру"""
        game = Game(
            game_id=game_id,
            user_id=user_id,  # Это будет user.id (INTEGER), а не telegram_id
            game_type=game_type,
            bet_amount=bet_amount,
            currency=currency,
            status=GameStatus.PENDING,
            payout=0.0
        )
        session.add(game)
        await session.commit()
        await session.refresh(game)
        return game
    
    @staticmethod
    async def get_by_game_id(session: AsyncSession, game_id: str) -> Optional[Game]:
        """Получить игру по game_id"""
        result = await session.execute(
            select(Game).where(Game.game_id == game_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def complete_game(session: AsyncSession, game: Game, result: GameResult, payout: float):
        """Завершить игру"""
        game.status = GameStatus.COMPLETED
        game.result = result
        game.payout = payout
        game.completed_at = datetime.utcnow()
        await session.commit()


class TransactionCRUD:
    @staticmethod
    async def create(session: AsyncSession, user_id: int, invoice_id: str, 
                    amount: float, currency: str, status: str, game_id: str = None) -> Transaction:
        """Создать транзакцию"""
        # Получаем game.id по game_id (UUID)
        game_db_id = None
        if game_id:
            result = await session.execute(
                select(Game.id).where(Game.game_id == game_id)
            )
            game_db_id = result.scalar_one_or_none()
        
        # ✅ ИСПРАВЛЕНИЕ: Конвертируем invoice_id в строку
        invoice_id_str = str(invoice_id)
        
        transaction = Transaction(
            invoice_id=invoice_id_str,  # ✅ Строка
            user_id=user_id,  # Это user.id (INTEGER)
            game_id=game_db_id,  # Это game.id (INTEGER)
            amount=amount,
            currency=currency,
            status=TransactionStatus.PENDING if status == "pending" else TransactionStatus.PAID
        )
        session.add(transaction)
        await session.commit()
        await session.refresh(transaction)
        return transaction
    
    @staticmethod
    async def get_by_invoice_id(session: AsyncSession, invoice_id: str) -> Optional[Transaction]:
        """Получить транзакцию по invoice_id"""
        result = await session.execute(
            select(Transaction).where(Transaction.invoice_id == invoice_id)
        )
        return result.scalar_one_or_none()
    
    @staticmethod
    async def update_status(session: AsyncSession, transaction: Transaction, status: TransactionStatus):
        """Обновить статус транзакции"""
        transaction.status = status
        if status == TransactionStatus.PAID:
            transaction.paid_at = datetime.utcnow()
        await session.commit()