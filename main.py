from fastapi import FastAPI, HTTPException, Depends, Path, Query
from pydantic import BaseModel
from pymongo import MongoClient
from passlib.context import CryptContext
from pydantic import BaseModel
from uuid import uuid4
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta



# 앱 생성
app = FastAPI()

# JWT 관련 상수 및 암호화 설정
SECRET_KEY = "super-secret-kyunghee-morning123!"  # 실제 서비스에서는 환경변수로 관리
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# OAuth2 설정 
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 비밀번호 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# MongoDB Atlas 클러스터 연결
client = MongoClient("mongodb+srv://jegalhhh:1234@morning-cluster.rjlkphg.mongodb.net/?retryWrites=true&w=majority&appName=morning-cluster")
db = client["morning_db"]

# 컬렉션 정의
users_collection = db["users"]
rooms_collection = db["morning_rooms"]

# JWT 토큰 생성 함수
def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# access_token으로 현재 로그인한 사용자 정보를 가져오는 함수
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="인증 정보가 유효하지 않습니다.",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = users_collection.find_one({"username": username})
    if user is None:
        raise credentials_exception

    return user

# 회원가입 요청용
class UserSignup(BaseModel):
    phone: str
    name: str
    student_id: str
    department: str
    username: str
    password: str

# 로그인 요청용 (현재 미사용, Swagger 내 form 방식으로 대체)
class UserLogin(BaseModel):
    username: str
    password: str

# 모닝방 생성 요청용
class RoomCreate(BaseModel):
    title: str
    wake_date: str  # "2025-04-07"
    wake_time: str  # "08:30"
    is_private: bool

# (현재 미사용) 모닝방 참여 요청용
class JoinRoomRequest(BaseModel):
    username: str

# 회원가입 API
# 회원가입 정보 (username, password 등)를 받아 DB에 저장
@app.post("/signup")
def signup(user: UserSignup):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

    hashed_pw = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_pw
    users_collection.insert_one(user_dict)

    return {"msg": "회원가입 성공!"}

# JWT 토큰 발급용 로그인 API
# 클라이언트는 이 API를 통해 access_token을 발급받아야 함
@app.post("/token")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = users_collection.find_one({"username": form_data.username})
    if not user or not pwd_context.verify(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호 오류")

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}


# 마이페이지 조회 API (로그인 필요)
# access_token으로 로그인한 사용자의 정보(username, 학과, 평판, 프로필사진 등)를 반환
@app.get("/me")
def get_my_profile(user: dict = Depends(get_current_user)):
    return {
        "username": user["username"],
        "name": user["name"],
        "department": user["department"],
        "reputation": user.get("reputation", 0),
        "profile_image": user.get("profile_image", "")
    }



# 모닝방 생성 API (로그인 필요)
# 로그인한 사용자가 모닝방을 생성함. 방 제목, 날짜, 시간, 공개 여부 입력
@app.post("/rooms")
def create_room(room: RoomCreate, user: dict = Depends(get_current_user)):
    room_id = str(uuid4())[:8]
    room_data = room.dict()
    room_data.update({
        "room_id": room_id,
        "created_at": datetime.utcnow().isoformat(),
        "created_by": user["username"],  
        "participants": [user["username"]]
    })

    rooms_collection.insert_one(room_data)
    return {"msg": "모닝방이 생성되었습니다!", "room_id": room_id}


# 공개된 모닝방 리스트 조회 API (로그인 불필요)
# 공개방만 정렬하여 리스트로 반환.
@app.get("/rooms")
def list_public_rooms():
    rooms = list(rooms_collection.find({"is_private": False}).sort("wake_date", 1))
    
    result = []
    for room in rooms:
        result.append({
            "room_id": room["room_id"],
            "title": room["title"],  
            "created_by": room["created_by"],
            "wake_date": room["wake_date"],
            "wake_time": room["wake_time"]
        })

    return result


# 모닝방 상세 정보 조회 API (로그인 불필요)
# room_id를 통해 방 상세 정보 확인
@app.get("/rooms/{room_id}")
def get_room_detail(room_id: str = Path(...)):
    room = rooms_collection.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="모닝방을 찾을 수 없습니다.")

    # 현재 시간과 기상 시간 계산
    now = datetime.utcnow()
    try:
        target_dt = datetime.strptime(f"{room['wake_date']} {room['wake_time']}", "%Y-%m-%d %H:%M")
        diff = target_dt - now
        minutes_left = int(diff.total_seconds() // 60)

        if minutes_left > 0:
            time_left = f"{minutes_left}분 후"
        elif -10 <= minutes_left <= 0:
            time_left = "기상 시간!"
        else:
            time_left = "기상 시간 지남"
    except:
        time_left = "시간 계산 오류"

    return {
        "room_id": room["room_id"],
        "title": room["title"],
        "created_by": room["created_by"],
        "wake_date": room["wake_date"],
        "wake_time": room["wake_time"],
        "is_private": room["is_private"],
        "time_left": time_left  # ⏱ 기상까지 남은 시간
    }


# 모닝방 참여하기 API (로그인 필요)
# 로그인한 사용자가 특정 room_id의 모닝방에 참여 (중복 참여 방지)
@app.post("/rooms/{room_id}/join")
def join_room(room_id: str, user: dict = Depends(get_current_user)):
    room = rooms_collection.find_one({"room_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="모닝방을 찾을 수 없습니다.")

    username = user["username"]

    if username in room.get("participants", []):
        return {"msg": "이미 참여한 사용자입니다.", "participants": room["participants"]}

    rooms_collection.update_one(
        {"room_id": room_id},
        {"$push": {"participants": username}}
    )

    updated_room = rooms_collection.find_one({"room_id": room_id})
    return {"msg": "참여 완료!", "participants": updated_room["participants"]}
