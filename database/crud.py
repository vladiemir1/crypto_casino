from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Game, Transaction, GameStatus, GameResult, TransactionStatus
from datetime import datetime
from typing import Optional, Union, List
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

class UserCRUD:
    """Класс для работы с моделью User"""

    @staticmethod
    async def get_or_create(session: AsyncSession, telegram_id: int, username: str = None, first_name: str = None) -> User:
        """Получить или создать пользователя по telegram_id"""
        try:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                user = User(
                    telegram_id=telegram_id,
                    username=username or f"user_{telegram_id}",
                    first_name=first_name,
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                logger.info(f"Создан новый пользователь: telegram_id={telegram_id}, username={username}")
            else:
                logger.debug(f"Найден существующий пользователь: telegram_id={telegram_id}")
            return user
        except Exception as e:
            logger.error(f"Ошибка при создании/получении пользователя: {e}")
            raise

    @staticmethod
    async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
        """Получить пользователя по telegram_id"""
        try:
            result = await session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalar_one_or_none()
            logger.debug(f"Поиск пользователя по telegram_id={telegram_id}: {'Найден' if user else 'Не найден'}")
            return user
        except Exception as e:
            logger.error(f"Ошибка при поиске пользователя: {e}")
            raise

    @staticmethod
    async def update_stats(session: AsyncSession, user: User, wagered: float = 0.0, won: float = 0.0, games: int = 0) -> None:
        """Обновить статистику пользователя"""
        try:
            user.total_wagered += wagered
            user.total_won += won
            user.games_played += games
            user.last_activity = datetime.utcnow()
            await session.commit()
            logger.info(f"Обновлена статистика пользователя {user.id}: wagered={user.total_wagered}, won={user.total_won}, games={user.games_played}")
        except Exception as e:
            logger.error(f"Ошибка при обновлении статистики пользователя {user.id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_stats(session: AsyncSession, user_id: int) -> dict:
        """Получить статистику пользователя"""
        try:
            result = await session.execute(
                select(User.total_wagered, User.total_won, User.games_played).where(User.id == user_id)
            )
            stats = result.fetchone()
            return {
                "total_wagered": stats[0] if stats else 0.0,
                "total_won": stats[1] if stats else 0.0,
                "games_played": stats[2] if stats else 0
            } if stats else {"total_wagered": 0.0, "total_won": 0.0, "games_played": 0}
        except Exception as e:
            logger.error(f"Ошибка при получении статистики пользователя {user_id}: {e}")
            raise


class GameCRUD:
    """Класс для работы с моделью Game"""

    @staticmethod
    async def create(session: AsyncSession, game_id: str, user_id: int, game_type: str,
                    bet_amount: float, currency: str = "USDT") -> Game:
        """Создать новую игру"""
        try:
            game = Game(
                game_id=game_id,
                user_id=user_id,
                game_type=game_type,
                bet_amount=bet_amount,
                currency=currency,
                status=GameStatus.PENDING,
                payout=0.0
            )
            session.add(game)
            await session.commit()
            await session.refresh(game)
            logger.info(f"Создана новая игра: game_id={game_id}, user_id={user_id}, type={game_type}")
            return game
        except Exception as e:
            logger.error(f"Ошибка при создании игры {game_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_by_game_id(session: AsyncSession, game_id: str) -> Optional[Game]:
        """Получить игру по game_id"""
        try:
            result = await session.execute(
                select(Game).where(Game.game_id == game_id)
            )
            game = result.scalar_one_or_none()
            logger.debug(f"Поиск игры по game_id={game_id}: {'Найдена' if game else 'Не найдена'}")
            return game
        except Exception as e:
            logger.error(f"Ошибка при поиске игры {game_id}: {e}")
            raise

    @staticmethod
    async def complete_game(session: AsyncSession, game: Game, result: GameResult, payout: float) -> None:
        """Завершить игру и обновить статистику пользователя"""
        try:
            game.status = GameStatus.COMPLETED
            game.result = result
            game.payout = payout
            game.completed_at = datetime.utcnow()

            # Обновляем статистику пользователя
            user = await session.get(User, game.user_id)
            if user:
                await UserCRUD.update_stats(session, user, wagered=game.bet_amount, won=payout if result == GameResult.WIN else 0.0, games=1)

            await session.commit()
            logger.info(f"Игра завершена: game_id={game.game_id}, result={result}, payout={payout}")
        except Exception as e:
            logger.error(f"Ошибка при завершении игры {game.game_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_user_games(session: AsyncSession, user_id: int) -> List[Game]:
        """Получить все игры пользователя"""
        try:
            result = await session.execute(
                select(Game).where(Game.user_id == user_id).order_by(Game.created_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении игр пользователя {user_id}: {e}")
            raise


class TransactionCRUD:
    """Класс для работы с моделью Transaction"""

    @staticmethod
    async def create(session: AsyncSession,
                     user_id: int,
                     invoice_id: Union[str, int],
                     amount: float,
                     currency: str = "USDT",
                     status: Union[str, TransactionStatus] = TransactionStatus.PENDING,
                     game_id: Optional[str] = None,
                     pay_url: Optional[str] = None) -> Transaction:
        """
        Создать транзакцию.
        Поддерживает:
         - invoice_id как str/int (нормализуется в строку)
         - status как строку 'pending'/'paid'/'expired' или как TransactionStatus
         - необязательный pay_url
         - game_id — UUID game.game_id (по нему ищется game.id)
        """
        try:
            # Получаем game.id по game_id (UUID)
            game_db_id = None
            if game_id:
                game = await GameCRUD.get_by_game_id(session, game_id)
                game_db_id = game.id if game else None

            # Нормализация invoice_id в строку
            invoice_id_str = str(invoice_id)

            # Нормализация статуса
            if isinstance(status, TransactionStatus):
                status_enum = status
            else:
                s = str(status).strip().lower()
                if s in ("pending", "p"):
                    status_enum = TransactionStatus.PENDING
                elif s in ("paid", "p"):
                    status_enum = TransactionStatus.PAID
                else:
                    status_enum = TransactionStatus.EXPIRED

            transaction = Transaction(
                invoice_id=invoice_id_str,
                user_id=user_id,
                game_id=game_db_id,
                amount=amount,
                currency=currency,
                status=status_enum,
                pay_url=pay_url
            )
            session.add(transaction)
            await session.commit()
            await session.refresh(transaction)
            logger.info(f"Создана транзакция: invoice_id={invoice_id_str}, user_id={user_id}, status={status_enum}")
            return transaction
        except Exception as e:
            logger.error(f"Ошибка при создании транзакции {invoice_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_by_invoice_id(session: AsyncSession, invoice_id: Union[str, int]) -> Optional[Transaction]:
        """Получить транзакцию по invoice_id (нормализуем входной id в строку)"""
        try:
            invoice_id_str = str(invoice_id)
            result = await session.execute(
                select(Transaction).where(Transaction.invoice_id == invoice_id_str)
            )
            transaction = result.scalar_one_or_none()
            logger.debug(f"Поиск транзакции по invoice_id={invoice_id_str}: {'Найдена' if transaction else 'Не найдена'}")
            return transaction
        except Exception as e:
            logger.error(f"Ошибка при поиске транзакции {invoice_id}: {e}")
            raise

    @staticmethod
    async def update_status(session: AsyncSession, transaction: Transaction, status: Union[str, TransactionStatus]) -> Transaction:
        """Обновить статус транзакции (принимает строку или TransactionStatus)"""
        try:
            if isinstance(status, TransactionStatus):
                transaction.status = status
            else:
                s = str(status).strip().lower()
                if s in ("pending", "p"):
                    transaction.status = TransactionStatus.PENDING
                elif s in ("paid", "p"):
                    transaction.status = TransactionStatus.PAID
                else:
                    transaction.status = TransactionStatus.EXPIRED

            if transaction.status == TransactionStatus.PAID:
                transaction.paid_at = datetime.utcnow()
            elif transaction.status == TransactionStatus.EXPIRED:
                transaction.paid_at = None  # Сбрасываем время оплаты при истечении

            await session.commit()
            await session.refresh(transaction)
            logger.info(f"Обновлён статус транзакции {transaction.invoice_id}: {transaction.status}")
            return transaction
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса транзакции {transaction.invoice_id}: {e}")
            await session.rollback()
            raise

    @staticmethod
    async def get_user_transactions(session: AsyncSession, user_id: int) -> List[Transaction]:
        """Получить все транзакции пользователя"""
        try:
            result = await session.execute(
                select(Transaction).where(Transaction.user_id == user_id).order_by(Transaction.created_at.desc())
            )
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Ошибка при получении транзакций пользователя {user_id}: {e}")
            raise