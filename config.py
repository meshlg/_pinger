from collections import deque
from typing import Deque, Dict, Any, TypedDict
from datetime import datetime
import locale

VERSION = "2.1.5"

# Supported languages
SUPPORTED_LANGUAGES = ["en", "ru"]

def _detect_system_language() -> str:
    """Detect system language and return supported language code."""
    try:
        # Get system locale
        system_locale = locale.getdefaultlocale()[0]
        if system_locale:
            lang_code = system_locale.lower()[:2]
            # Map common Russian locale codes
            if lang_code in ("ru", "be", "uk", "kk"):
                return "ru"
        # Check environment variable as fallback
        import os
        env_lang = os.environ.get("LANG", "")
        if "ru" in env_lang.lower():
            return "ru"
    except Exception:
        pass
    return "en"

CURRENT_LANGUAGE = _detect_system_language()
TARGET_IP = "1.1.1.1"
INTERVAL = 1
WINDOW_SIZE = 1800
LATENCY_WINDOW = 600

ENABLE_SOUND_ALERTS = True
ALERT_COOLDOWN = 5
ALERT_ON_PACKET_LOSS = True
ALERT_ON_HIGH_LATENCY = True
HIGH_LATENCY_THRESHOLD = 100

ENABLE_THRESHOLD_ALERTS = True
PACKET_LOSS_THRESHOLD = 5.0
AVG_LATENCY_THRESHOLD = 100
CONSECUTIVE_LOSS_THRESHOLD = 5
JITTER_THRESHOLD = 30

ENABLE_IP_CHANGE_ALERT = True
IP_CHECK_INTERVAL = 15
IP_CHANGE_SOUND = True
LOG_IP_CHANGES = True

ENABLE_DNS_MONITORING = True
DNS_TEST_DOMAIN = "cloudflare.com"
DNS_CHECK_INTERVAL = 10
DNS_SLOW_THRESHOLD = 100

# DNS record types to test (requires dnspython)
DNS_RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]

# DNS Benchmark tests (Cached/Uncached/DotCom)
ENABLE_DNS_BENCHMARK = True
DNS_BENCHMARK_DOTCOM_DOMAIN = "cloudflare.com"  # Domain for DotCom test
DNS_BENCHMARK_SERVERS = ["system"]  # "system" uses system resolver, or list IPs: ["1.1.1.1", "8.8.8.8"]
DNS_BENCHMARK_HISTORY_SIZE = 50  # Number of queries to keep for statistics

ENABLE_AUTO_TRACEROUTE = False  # Disabled — traceroute only on manual trigger or route change
TRACEROUTE_TRIGGER_LOSSES = 3
TRACEROUTE_COOLDOWN = 300       # Min interval (seconds)
TRACEROUTE_MAX_HOPS = 15

ENABLE_MTU_MONITORING = True
MTU_CHECK_INTERVAL = 30
ENABLE_PATH_MTU_DISCOVERY = True
PATH_MTU_CHECK_INTERVAL = 120
DEFAULT_MTU = 1500

# MTU issue detection hysteresis
MTU_ISSUE_CONSECUTIVE = 3  # how many consecutive failing checks to mark an MTU issue
MTU_CLEAR_CONSECUTIVE = 2  # how many consecutive OK checks to clear the MTU issue
MTU_DIFF_THRESHOLD = 50    # minimal difference between local and path MTU to consider an issue (bytes)


ENABLE_TTL_MONITORING = True
TTL_CHECK_INTERVAL = 10

ENABLE_HOP_MONITORING = True
HOP_PING_INTERVAL = 1          # seconds between hop ping cycles
HOP_PING_TIMEOUT = 0.5         # seconds per hop ping (500ms for fast response)
HOP_REDISCOVER_INTERVAL = 3600 # Once per hour only
HOP_LATENCY_GOOD = 50          # ms — green threshold
HOP_LATENCY_WARN = 100         # ms — yellow threshold (above = red)

ENABLE_PROBLEM_ANALYSIS = True
PROBLEM_ANALYSIS_INTERVAL = 60
PROBLEM_HISTORY_SIZE = 100
PREDICTION_WINDOW = 300
# Suppress repetitive logs for problems and route changes (seconds)
PROBLEM_LOG_SUPPRESSION_SECONDS = 6000
ROUTE_LOG_SUPPRESSION_SECONDS = 6000

ENABLE_ROUTE_ANALYSIS = True
ROUTE_ANALYSIS_INTERVAL = 1800  # Check route every 30 min
ROUTE_HISTORY_SIZE = 10
HOP_TIMEOUT_THRESHOLD = 3000

# Route change detection settings
ROUTE_CHANGE_CONSECUTIVE = 2  # consecutive detections to consider route changed
ROUTE_CHANGE_HOP_DIFF = 2     # minimal number of changed hops to consider significant
ROUTE_IGNORE_FIRST_HOPS = 2   # ignore changes in first N hops (local network)
ROUTE_SAVE_ON_CHANGE_CONSECUTIVE = 2  # save traceroute after N consecutive changes

SHOW_VISUAL_ALERTS = True
ALERT_DISPLAY_TIME = 10
ALERT_PANEL_LINES = 3
MAX_ACTIVE_ALERTS = 3

# Metrics / health endpoint
ENABLE_METRICS = True
METRICS_ADDR = "0.0.0.0"
METRICS_PORT = 8000
ENABLE_HEALTH_ENDPOINT = True
HEALTH_ADDR = "0.0.0.0"
HEALTH_PORT = 8001

import os

LOG_DIR = os.path.expanduser("~/.pinger")
LOG_FILE = os.path.join(LOG_DIR, "ping_monitor.log")
LOG_LEVEL = "INFO"

# If True, truncate (clear) log file at startup
LOG_TRUNCATE_ON_START = True

LANG: Dict[str, Dict[str, str]] = {
    "ru": {
        # ── General ──
        "title": "Сетевой монитор",
        "start": "Запуск сетевого монитора для {target}...",
        "stop": "Мониторинг остановлен.",
        "press": "Нажмите Ctrl+C для остановки.",
        "na": "N/A",
        "ms": "мс",
        "never": "Никогда",
        "just_now": "Только что",
        "ago": "назад",
        "ok": "OK",
        "slow": "Медленно",
        "failed": "Ошибка",
        "error": "Ошибка",
        "none_label": "Нет",
        # ── Time units ──
        "time_d": "д",
        "time_h": "ч",
        "time_m": "м",
        "time_s": "с",
        # ── Status ──
        "status_ok": "OK",
        "status_timeout": "Таймаут",
        "status_connected": "ПОДКЛЮЧЕНО",
        "status_disconnected": "НЕТ СВЯЗИ",
        "status_degraded": "ДЕГРАДАЦИЯ",
        "status_timeout_bar": "ТАЙМАУТ",
        "status_waiting": "ОЖИДАНИЕ",
        # ── Section headers ──
        "conn": "ПОДКЛЮЧЕНИЕ",
        "stats": "СТАТИСТИКА",
        "lat": "ЗАДЕРЖКА",
        "mon": "МОНИТОРИНГ",
        "alerts": "УВЕДОМЛЕНИЯ",
        "analysis": "АНАЛИЗ",
        "notifications": "УВЕДОМЛЕНИЯ",
        # ── Latency panel ──
        "current": "Текущий",
        "best": "Лучший",
        "average": "Средний",
        "peak": "Пиковый",
        "median": "Медиана",
        "jitter": "Джиттер",
        "spread": "Разброс",
        "latency_chart": "Задержка (последние значения):",
        "no_data": "нет данных",
        "waiting": "ожидание...",
        # ── Stats panel ──
        "sent": "Отправлено",
        "ok_count": "OK",
        "lost": "Потеряно",
        "losses": "Потери",
        "success_rate": "Успех",
        "loss_30m": "Потери 30м",
        "consecutive": "Подряд потерь",
        "max_label": "Макс",
        # ── MTU / TTL ──
        "mtu": "MTU",
        "path_mtu": "Path MTU",
        "mtu_ok": "OK",
        "mtu_low": "Снижен",
        "mtu_fragmented": "Фрагментация",
        "mtu_status_label": "MTU статус",
        "mtu_issues_label": "MTU проблем",
        "checks_unit": "проверок",
        "ttl": "TTL",
        "hops": "Хопов",
        "hop_unit": "хоп",
        "hops_unit": "хопов",
        # ── Problem analysis ──
        "problem_analysis": "АНАЛИЗ ПРОБЛЕМ",
        "problem_type": "Тип проблемы",
        "problem_none": "Нет проблем",
        "problem_isp": "Проблема ISP",
        "problem_local": "Локальная сеть",
        "problem_dns": "Проблема DNS",
        "problem_mtu": "Проблема MTU",
        "problem_unknown": "Неизвестно",
        "prediction": "Прогноз",
        "prediction_stable": "Стабильно",
        "prediction_risk": "Риск проблем",
        "pattern": "Паттерн",
        "last_problem": "Последняя",
        # ── Route analysis ──
        "route_analysis": "АНАЛИЗ МАРШРУТА",
        "route_label": "Маршрут",
        "hops_count": "Хопов",
        "problematic_hop": "Проблемный хоп",
        "problematic_hop_short": "Пробл.хоп",
        "route_changed": "Маршрут изменен",
        "route_stable": "Маршрут стабилен",
        "hop_latency": "Задержка хопа",
        "avg_latency": "Средняя задержка",
        "avg_latency_short": "Ср.задержка",
        "changed_hops": "Изменено",
        "changes": "Изменения",
        # ── Hop monitoring ──
        "hop_health": "ЗДОРОВЬЕ ХОПОВ",
        "hop_discovering": "Обнаружение хопов...",
        "hop_none": "Нет данных",
        "hop_good": "OK",
        "hop_slow": "Медл.",
        "hop_down": "Недост.",
        "hop_worst": "Худший",
        "hop_loss_label": "Потери",
        "hop_col_num": "#",
        "hop_col_min": "Мин",
        "hop_col_avg": "Ср",
        "hop_col_last": "Посл",
        "hop_col_loss": "Потери",
        "hop_col_host": "Хост",
        # ── Monitoring panel ──
        "alerts_label": "Тревоги",
        "traceroute_running": "Идет...",
        "alerts_off": "ВЫКЛ",
        "no_alerts": "Нет уведомлений.",
        # ── Footer ──
        "footer": "Ctrl+C — остановка  │  Логи: {log_file}",
        "update_available": "Обновление доступно: {current} → {latest} — pipx upgrade network-pinger",
        # ── Alert messages (monitor.py) ──
        "alert_ip_changed": "IP изменен: {old} -> {new}",
        "alert_high_loss": "Высокие потери (30м): {val:.1f}%",
        "alert_loss_normalized": "Потери нормализовались",
        "alert_high_avg_latency": "Высокая средняя задержка: {val:.1f}мс",
        "alert_latency_normalized": "Задержка нормализовалась",
        "alert_connection_lost": "Соединение потеряно ({n} подряд)",
        "alert_connection_restored": "Соединение восстановлено",
        "alert_high_jitter": "Высокий джиттер: {val:.1f}мс",
        "alert_jitter_normalized": "Джиттер нормализовался",
        # ── Main app ──
        "uptime_label": "Время работы",
        "bg_stopped": "Все фоновые потоки остановлены.",
        # ── Dependency check ──
        "err_missing_commands": "Ошибка: отсутствуют системные команды: {cmds}",
        "install_commands_hint": "Для установки системных команд:",
        "win_ping_hint": "  ping и tracert входят в стандартную установку Windows",
        "win_tracert_hint": "  Если traceroute отсутствует, установите пакет 'tracert' из репозитория",
        "err_missing_deps": "Ошибка: отсутствуют зависимости:",
        "install_deps_hint": "Для установки выполните:",
        # ── Traceroute service ──
        "traceroute_not_found": "Traceroute: команда не найдена",
        "traceroute_timeout": "Traceroute: таймаут",
        "traceroute_starting": "Traceroute: запуск...",
        "traceroute_saved": "Traceroute сохранен: {file}",
        "traceroute_save_failed": "Не удалось сохранить traceroute",
    },
    "en": {
        # ── General ──
        "title": "Network Monitor",
        "start": "Starting network monitor for {target}...",
        "stop": "Monitoring stopped.",
        "press": "Press Ctrl+C to stop.",
        "na": "N/A",
        "ms": "ms",
        "never": "Never",
        "just_now": "Just now",
        "ago": "ago",
        "ok": "OK",
        "slow": "Slow",
        "failed": "Failed",
        "error": "Error",
        "none_label": "None",
        # ── Time units ──
        "time_d": "d",
        "time_h": "h",
        "time_m": "m",
        "time_s": "s",
        # ── Status ──
        "status_ok": "OK",
        "status_timeout": "Timeout",
        "status_connected": "CONNECTED",
        "status_disconnected": "DISCONNECTED",
        "status_degraded": "DEGRADED",
        "status_timeout_bar": "TIMEOUT",
        "status_waiting": "WAITING",
        # ── Section headers ──
        "conn": "CONNECTION",
        "stats": "STATISTICS",
        "lat": "LATENCY",
        "mon": "MONITORING",
        "alerts": "ALERTS",
        "analysis": "ANALYSIS",
        "notifications": "NOTIFICATIONS",
        # ── Latency panel ──
        "current": "Current",
        "best": "Best",
        "average": "Average",
        "peak": "Peak",
        "median": "Median",
        "jitter": "Jitter",
        "spread": "Spread",
        "latency_chart": "Latency (recent values):",
        "no_data": "no data",
        "waiting": "waiting...",
        # ── Stats panel ──
        "sent": "Sent",
        "ok_count": "OK",
        "ok_label": "OK",
        "lost": "Lost",
        "losses": "Losses",
        "success_rate": "Success",
        "loss_30m": "Loss 30m",
        "consecutive": "Consecutive",
        "max_label": "Max",
        # ── MTU / TTL ──
        "mtu": "MTU",
        "path_mtu": "Path MTU",
        "mtu_ok": "OK",
        "mtu_low": "Reduced",
        "mtu_fragmented": "Fragmented",
        "mtu_status_label": "MTU status",
        "mtu_issues_label": "MTU issues",
        "checks_unit": "checks",
        "ttl": "TTL",
        "hops": "Hops",
        "hop_unit": "hop",
        "hops_unit": "hops",
        # ── Problem analysis ──
        "problem_analysis": "PROBLEM ANALYSIS",
        "problem_type": "Problem Type",
        "problem_none": "No Problems",
        "problem_isp": "ISP Issue",
        "problem_local": "Local Network",
        "problem_dns": "DNS Issue",
        "problem_mtu": "MTU Issue",
        "problem_unknown": "Unknown",
        "prediction": "Prediction",
        "prediction_stable": "Stable",
        "prediction_risk": "Risk of Problems",
        "pattern": "Pattern",
        "last_problem": "Last",
        # ── Route analysis ──
        "route_analysis": "ROUTE ANALYSIS",
        "route_label": "Route",
        "hops_count": "Hops",
        "problematic_hop": "Problematic Hop",
        "problematic_hop_short": "Probl. hop",
        "route_changed": "Route Changed",
        "route_stable": "Route Stable",
        "hop_latency": "Hop Latency",
        "avg_latency": "Avg Latency",
        "avg_latency_short": "Avg latency",
        "changed_hops": "Changed",
        "changes": "Changes",
        # ── Hop monitoring ──
        "hop_health": "HOP HEALTH",
        "hop_discovering": "Discovering hops...",
        "hop_none": "No data",
        "hop_good": "OK",
        "hop_slow": "Slow",
        "hop_down": "Down",
        "hop_worst": "Worst",
        "hop_loss_label": "Loss",
        "hop_col_num": "#",
        "hop_col_min": "Min",
        "hop_col_avg": "Avg",
        "hop_col_last": "Last",
        "hop_col_loss": "Loss",
        "hop_col_host": "Host",
        # ── Monitoring panel ──
        "alerts_label": "Alerts",
        "traceroute_running": "Running...",
        "alerts_off": "OFF",
        "no_alerts": "No notifications.",
        # ── Footer ──
        "footer": "Ctrl+C — stop  |  Logs: {log_file}",
        "update_available": "Update available: {current} → {latest} — pipx upgrade network-pinger",
        # ── Alert messages (monitor.py) ──
        "alert_ip_changed": "IP changed: {old} -> {new}",
        "alert_high_loss": "High packet loss (30m): {val:.1f}%",
        "alert_loss_normalized": "Packet loss normalized",
        "alert_high_avg_latency": "High avg latency: {val:.1f}ms",
        "alert_latency_normalized": "Latency normalized",
        "alert_connection_lost": "Connection lost ({n} consecutive)",
        "alert_connection_restored": "Connection restored",
        "alert_high_jitter": "High jitter: {val:.1f}ms",
        "alert_jitter_normalized": "Jitter normalized",
        # ── Main app ──
        "uptime_label": "Uptime",
        "bg_stopped": "All background threads stopped.",
        # ── Dependency check ──
        "err_missing_commands": "Error: missing system commands: {cmds}",
        "install_commands_hint": "To install system commands:",
        "win_ping_hint": "  ping and tracert are included in standard Windows installation",
        "win_tracert_hint": "  If traceroute is missing, install the 'tracert' package",
        "err_missing_deps": "Error: missing dependencies:",
        "install_deps_hint": "To install, run:",
        # ── Traceroute service ──
        "traceroute_not_found": "Traceroute: command not found",
        "traceroute_timeout": "Traceroute: timeout",
        "traceroute_starting": "Traceroute: starting...",
        "traceroute_saved": "Traceroute saved: {file}",
        "traceroute_save_failed": "Failed to save traceroute",
    },
}


def t(key: str) -> str:
    return LANG.get(CURRENT_LANGUAGE, LANG["ru"]).get(key, key)


class ThresholdStates(TypedDict):
    high_packet_loss: bool
    high_avg_latency: bool
    connection_lost: bool
    high_jitter: bool


class StatsDict(TypedDict):
    total: int
    success: int
    failure: int
    last_status: str
    last_latency_ms: str
    min_latency: float
    max_latency: float
    total_latency_sum: float
    latencies: Deque[float]
    consecutive_losses: int
    max_consecutive_losses: int
    public_ip: str
    country: str
    country_code: str | None
    start_time: datetime | None
    last_problem_time: datetime | None
    last_alert_time: datetime | None
    previous_ip: str | None
    ip_change_time: datetime | None
    active_alerts: list[Dict[str, Any]]
    threshold_states: ThresholdStates
    dns_resolve_time: float | None
    dns_status: str
    dns_results: Dict[str, Any]
    dns_benchmark: Dict[str, Any]
    last_traceroute_time: datetime | None
    traceroute_running: bool
    ping_missing_warned: bool
    jitter: float
    local_mtu: int | None
    path_mtu: int | None
    mtu_status: str
    mtu_consecutive_issues: int
    mtu_consecutive_ok: int
    mtu_last_status_change: datetime | None
    last_ttl: int | None
    ttl_hops: int | None
    ttl_history: Deque[int]
    current_problem_type: str
    problem_prediction: str
    problem_pattern: str
    problem_history: list[Dict[str, Any]]
    route_hops: list[Dict[str, Any]]
    route_problematic_hop: int | None
    route_changed: bool
    route_consecutive_changes: int
    route_consecutive_ok: int
    route_last_change_time: datetime | None
    route_last_diff_count: int
    route_history: list[Dict[str, Any]]


def create_stats() -> StatsDict:
    return {
        "total": 0,
        "success": 0,
        "failure": 0,
        "last_status": t("na"),
        "last_latency_ms": t("na"),
        "min_latency": float("inf"),
        "max_latency": 0.0,
        "total_latency_sum": 0.0,
        "latencies": deque(maxlen=LATENCY_WINDOW),
        "consecutive_losses": 0,
        "max_consecutive_losses": 0,
        "public_ip": "...",
        "country": "...",
        "country_code": None,
        "start_time": None,
        "last_problem_time": None,
        "last_alert_time": None,
        "previous_ip": None,
        "ip_change_time": None,
        "active_alerts": [],
        "threshold_states": {
            "high_packet_loss": False,
            "high_avg_latency": False,
            "connection_lost": False,
            "high_jitter": False,
        },
        "dns_resolve_time": None,
        "dns_status": "...",
        "dns_results": {},
        "dns_benchmark": {},
        "last_traceroute_time": None,
        "traceroute_running": False,
        "ping_missing_warned": False,
        "jitter": 0.0,
        "local_mtu": None,
        "path_mtu": None,
        "mtu_status": "...",
        "mtu_consecutive_issues": 0,
        "mtu_consecutive_ok": 0,
        "mtu_last_status_change": None,
        "last_ttl": None,
        "ttl_hops": None,
        "ttl_history": deque(maxlen=100),
        "current_problem_type": t("problem_none"),
        "problem_prediction": t("prediction_stable"),
        "problem_pattern": "...",
        "problem_history": [],
        "route_hops": [],
        "route_problematic_hop": None,
        "route_changed": False,
        "route_consecutive_changes": 0,
        "route_consecutive_ok": 0,
        "route_last_change_time": None,
        "route_last_diff_count": 0,
        "route_history": [],
        "last_route_change_time": None,
    }


def create_recent_results() -> Deque[bool]:
    return deque(maxlen=WINDOW_SIZE)
