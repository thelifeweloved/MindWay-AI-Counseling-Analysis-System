// config.js
const isLocal = window.location.port === "5500" || window.location.hostname === "localhost";

const API_BASE_URL = isLocal 
    ? "http://127.0.0.1:8000"  // 로컬에서 백엔드 서버(main.py) 주소
    : window.location.origin;  // 클라우드 배포 주소