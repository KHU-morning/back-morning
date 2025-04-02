"# morning-back" 


/signup

요청:
- phone: 전화번호
- name: 이름
- student_id: 학번
- department: 학과명
- username: 아이디
- password: 비밀번호 (암호화 저장됨)

응답:
- msg: 회원가입 성공 메시지


 /token

로그인 후 access_token 발급 API (JWT 사용)

요청 (x-www-form-urlencoded):
- username: 아이디
- password: 비밀번호

응답:
- access_token: JWT 토큰 문자열
- token_type: bearer


/me

마이페이지 조회 API (토큰 인증 필요)

응답:
- username: 사용자 아이디
- name: 이름
- department: 학과
- reputation: 평판 점수 (기본 0)
- profile_image: 프로필 사진 URL (없으면 빈 문자열)
"""


/rooms (POST)

모닝방 생성 API (토큰 인증 필요)

요청:
- title: 방 제목
- wake_date: 기상 날짜 ("YYYY-MM-DD")
- wake_time: 기상 시간 ("HH:MM")
- is_private: 비공개 여부 (True = 비공개)

※ created_by, participants 등은 백엔드에서 자동 설정됨

응답:
- msg: 생성 완료 메시지
- room_id: 생성된 고유 방 ID


/rooms (GET)

공개된 모닝방 리스트 조회 API

응답 (리스트):
- room_id: 방 ID
- title: 방 제목
- created_by: 생성자 ID
- wake_date: 기상 날짜
- wake_time: 기상 시간


/rooms/{room_id}

"""
모닝방 상세 정보 조회 API

요청:
- room_id: 조회할 방의 고유 ID

응답:
- room_id: 방 ID
- title: 방 제목
- created_by: 생성자 ID
- wake_date: 기상 날짜
- wake_time: 기상 시간
- is_private: 비공개 여부
"""


/rooms/{room_id}/join

모닝방 참여 API (토큰 인증 필요)

요청:
- room_id: 참여할 방 ID

응답:
- msg: 참여 완료 or 이미 참여한 사용자
- participants: 현재 방의 참여자 목록 (username 리스트)

