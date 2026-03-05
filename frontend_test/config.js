const isLocal = window.location.port === "5500"
  || window.location.hostname === "localhost"
  || window.location.hostname === "127.0.0.1";

const API_BASE_URL = isLocal
  ? "http://127.0.0.1:8001"  // 로컬 FastAPI
  : "http://223.130.143.55"; // 서버(nginx 80)