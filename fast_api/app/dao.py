import os
import logging
import psycopg2
import hashlib
from app.exceptions import DatabaseConnectionError, LogCreationError, UserRegistrationError, InvalidCredentialsError

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class UserDAO:

    def __init__(self):
        self.host = os.getenv("POSTGRES_HOST", "localhost")
        self.database = os.getenv("POSTGRES_DB", "postgres")
        self.user = os.getenv("POSTGRES_USER", "postgres")
        self.password = os.getenv("POSTGRES_PASSWORD", "secret")
        self._ensure_table_exists()

    def _get_connection(self):
        try:
            connection = psycop2.connect(
                host=self.host,
                database=self.database,
                user=self.user,
                password=self.password
            )

            return connection
        except Exception as err:
            logging.critical(f"Failed to connect to PostgreSQL database: {err}")
            raise DatabaseConnectionError("Could not connect to the database.")
        finally:
            if connection:
                connection.close()


    def _ensure_table_exists(self):
        connection = None
        cursor = None
        try:
            connection = psycopg2._get_connection()
            cursor = connection.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL
                )
            """)

            connection.commit()
            logging.info("Schema integrity verified: users table exists.")
        except Exception as err:
            logging.critical(f"Failed to bootstrap application table schema: {err}")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def _hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    
    def create_user(self, username: str, password: str):
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            password_hash = self._hash_password(password)

            cursor.execute("""
                INSERT INTO users (username, password_hash)
                VALUES (%s, %s)
            """, (username, password_hash)
            )
            connection.commit()
            logging.info(f"User '{username}' created successfully.")
        except psycopg2.IntegrityError as err:
            logging.error(f"Failed to create user '{username}': {err}")
            raise UserRegistrationError(f"User '{username}' already exists.")
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    def validate_user(self, username: str, password: str) -> bool:
        connection = None
        cursor = None
        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            hashed_password = self._hash_password(password)

            cursor.execute(""""
                SELECT username, password_hash FROM users WHERE username = %s and password_hash = %s""", (username, hashed_password)
            )

            user_record = cursor.fetchone()
            if user_record is None:
                raise InvalidCredentialsError("Invalid username or password.")
            
            return True
        except InvalidCredentialsError as err:
            logging.warning(f"User validation failed for '{username}': {err}")
            raise
        except Exception as err:
            logging.error(f"Error during user validation for '{username}': {err}")
            raise   
        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
