import configparser
import json
import logging
import sqlite3

from fastapi import FastAPI, Depends, HTTPException, APIRouter
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from passlib.context import CryptContext
from pydantic import BaseModel
from jose import JWTError, jwt
import datetime
from typing import Optional, Dict

from starlette import status


class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: str


class TokenData(BaseModel):
    username: Optional[str] = None


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


class UserInDB(User):
    hashed_password: str


class AuthFuncs:
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.USERS_DB_FILE = config.get("SQLITE", "db_file")
        self.SECRET_KEY = config.get("JWT", "SECRET_KEY")
        self.ALGORITHM = config.get("JWT", "ALGORITHM")

        # Ensure the SQLite database and users table exist
        self._create_users_table()

    def _create_users_table(self):
        conn = sqlite3.connect(self.USERS_DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            username TEXT UNIQUE NOT NULL,
                            email TEXT,
                            full_name TEXT,
                            disabled BOOLEAN DEFAULT 0,
                            hashed_password TEXT NOT NULL
                          )''')
        conn.commit()
        conn.close()

    def verify_password(self, plain_password, hashed_password):
        # Bcrypt has a 72-byte password length limit
        return self.pwd_context.verify(plain_password[:72], hashed_password)

    def get_user(self, username: str) -> Optional[UserInDB]:
        conn = sqlite3.connect(self.USERS_DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT username, email, full_name, disabled, hashed_password FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return UserInDB(
                username=row[0],
                email=row[1],
                full_name=row[2],
                disabled=row[3],
                hashed_password=row[4],
            )
        return None

    def authenticate_user(self, username: str, password: str):
        user = self.get_user(username)
        if not user:
            return False
        if not self.verify_password(password, user.hashed_password):
            return False
        return user

    def create_access_token(self, data: dict, expires_delta: Optional[datetime.timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.datetime.utcnow() + expires_delta
        else:
            expire = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def create_refresh_token(self, data: dict, expires_delta: Optional[datetime.timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.datetime.utcnow() + expires_delta
        else:
            expire = datetime.datetime.utcnow() + datetime.timedelta(days=7)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt

    def get_current_user(self, token: str = Depends(oauth2_scheme)):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise credentials_exception
            token_data = TokenData(username=username)
        except JWTError:
            raise credentials_exception

        user = self.get_user(username=token_data.username)
        if user is None:
            raise credentials_exception
        return user


def get_current_active_user(current_user: User = Depends(AuthFuncs().get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


router = APIRouter()


@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    config = configparser.ConfigParser()
    config.read('config.cfg')

    access_token_expire_minutes = config.getint("JWT", "ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_days = config.getint("JWT", "REFRESH_TOKEN_EXPIRE_DAYS")

    logger = logging.getLogger(__name__)

    auth_funcs = AuthFuncs()

    logger.info("Attempting to authenticate: {}".format(form_data.username))

    user = auth_funcs.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = datetime.timedelta(minutes=access_token_expire_minutes)
    refresh_token_expires = datetime.timedelta(days=refresh_token_expire_days)
    access_token = auth_funcs.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    refresh_token = auth_funcs.create_refresh_token(
        data={"sub": user.username}, expires_delta=refresh_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@router.post("/refresh", response_model=Token)
async def refresh_access_token(token_request: TokenRefreshRequest):
    config = configparser.ConfigParser()
    config.read('config.cfg')

    secret_key = config.get("JWT", "SECRET_KEY")
    algorithm = config.get("JWT", "ALGORITHM")
    access_token_expire_minutes = config.getint("JWT", "ACCESS_TOKEN_EXPIRE_MINUTES")

    logger = logging.getLogger(__name__)

    auth_funcs = AuthFuncs()

    logger.info("Processing refresh request...")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token_request.refresh_token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = auth_funcs.get_user(username=token_data.username)
    if user is None:
        raise credentials_exception

    access_token_expires = datetime.timedelta(minutes=access_token_expire_minutes)
    access_token = auth_funcs.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": token_request.refresh_token}


@router.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user