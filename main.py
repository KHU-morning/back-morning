from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from passlib.context import CryptContext
from fastapi import Query
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime


# 1. 앱 객체 생성
app = FastAPI()

# 2. DB 연결
client = MongoClient("mongodb+srv://jegalhhh:1234@morning-cluster.rjlkphg.mongodb.net/?retryWrites=true&w=majority&appName=morning-cluster")
db = client["morning_db"]
users_collection = db["users"]
rooms_collection = db["morning_rooms"]

# 3. 비밀번호 암호화 설정
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# 4. 모델 정의
class UserSignup(BaseModel):
    phone: str
    name: str
    student_id: str
    department: str
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

# 모닝방 생성용 DB 생성성

class RoomCreate(BaseModel):
    created_by: str
    title: str
    goal: str
    wake_date: str  # "2025-04-07"
    wake_time: str  # "08:30"
    is_private: bool

# 5. 회원가입 API
@app.post("/signup")
def signup(user: UserSignup):
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")

    hashed_pw = pwd_context.hash(user.password)
    user_dict = user.dict()
    user_dict["password"] = hashed_pw
    users_collection.insert_one(user_dict)

    return {"msg": "회원가입 성공!"}

# 6. 로그인 API
@app.post("/login")
def login(user: UserLogin):
    found = users_collection.find_one({"username": user.username})
    if not found:
        raise HTTPException(status_code=404, detail="존재하지 않는 아이디입니다.")

    if not pwd_context.verify(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="비밀번호가 틀렸습니다.")

    return {"msg": "로그인 성공!"}

# 7. 마이페이지 api
# 아이디, 평판, 프로필 사진, 학과 정보를 가져옵니다.
@app.get("/me")
def get_my_profile(username: str = Query(...)):
    user = users_collection.find_one({"username": username})
    if not user:
        raise HTTPException(status_code=404, detail="해당 유저를 찾을 수 없습니다.")

    return {
        "username": user["username"],
        "name": user["name"],
        "department": user["department"],
        "reputation": user.get("reputation", 0),
        "profile_image": user.get("profile_image", "")
    }


# 7. 모닝방 생성 api
@app.post("/rooms")
def create_room(room: RoomCreate):
    room_id = str(uuid4())[:8]  # 방 ID는 짧게 생성
    room_data = room.dict()
    room_data.update({
        "room_id": room_id,
        "created_at": datetime.utcnow().isoformat(),
        "participants": [room.created_by]
    })

    rooms_collection.insert_one(room_data)
    return {"msg": "모닝방이 생성되었습니다!", "room_id": room_id}
