# Улучшения панели хопов — Подробный план

## Анализ текущей реализации

### Существующая архитектура
- **[`services/hop_monitor_service.py`](services/hop_monitor_service.py)** — сервис мониторинга хопов
  - [`HopStatus`](services/hop_monitor_service.py:23) dataclass с полями: `hop_number`, `ip`, `hostname`, `last_latency`, `avg_latency`, `min_latency`, `max_latency`, `loss_count`, `total_pings`, `last_ok`, `latency_history`
  - [`LATENCY_HISTORY_SIZE = 30`](services/hop_monitor_service.py:60) — размер истории
  - [`to_dict()`](services/hop_monitor_service.py:42) — сериализация для UI

- **[`ui.py`](ui.py)** — рендеринг
  - [`render_hop_panel()`](ui.py:547) — основная функция
  - Таблица с колонками: `#`, `min`, `avg`, `last`, `loss`, `host`
  - Цветовая схема: red/yellow/green для loss

---

## Этап 1: Базовые метрики (2-3 часа)

### 1.1 Добавить jitter в HopStatus
```python
# services/hop_monitor_service.py
@dataclass
class HopStatus:
    # ... существующие поля ...
    jitter: float = 0.0
    prev_latency: Optional[float] = None  # для delta
    latency_delta: float = 0.0
    last_success_time: Optional[float] = None  # для uptime
```

**Изменения в [`_update_hop_status()`](services/hop_monitor_service.py:299):**
```python
def _update_hop_status(self, hop: HopStatus, ok: bool, latency: Optional[float]) -> None:
    with self._lock:
        hop.total_pings += 1
        hop.last_ok = ok
        
        if ok and latency is not None:
            # Delta (изменение vs предыдущий ping)
            if hop.prev_latency is not None:
                hop.latency_delta = latency - hop.prev_latency
            hop.prev_latency = latency
            
            # Jitter (простое скользящее среднее отклонение)
            if len(hop.latency_history) >= 2:
                import statistics
                hop.jitter = statistics.stdev(hop.latency_history)
            
            hop.last_latency = latency
            hop.latency_history.append(latency)
            # ... остальное
```

### 1.2 Обновить to_dict()
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        # ... существующие поля ...
        "jitter": self.jitter,
        "latency_delta": self.latency_delta,
    }
```

### 1.3 Обновить UI
В [`render_hop_panel()`](ui.py:570) добавить колонки:
```python
tbl.add_column(t("hop_col_delta"), width=7, justify="right")  # +0ms / -5ms
tbl.add_column(t("hop_col_jitter"), width=7, justify="right")  # 3ms
```

---

## Этап 2: Визуальные улучшения (3-4 часа)

### 2.1 Спарклайны (Sparklines)
```python
# ui.py
def _render_sparkline(history: list[float]) -> str:
    """Рендер мини-графика из истории latency."""
    if not history or len(history) < 2:
        return ""
    
    # Нормализация к 5 уровням
    min_val, max_val = min(history), max(history)
    range_val = max_val - min_val if max_val != min_val else 1
    
    chars = " ▁▂▃▅▇"  # 6 уровней (индекс 0-5)
    
    result = []
    for val in history[-10:]:  # последние 10 значений
        idx = min(5, int((val - min_val) / range_val * 5))
        result.append(chars[idx])
    
    return "".join(result)
```

### 2.2 Стрелки тренда
```python
# ui.py
def _render_trend_arrow(delta: float, threshold: float = 2.0) -> str:
    """Рендер стрелки тренда."""
    if delta > threshold:
        return "↑"  # растёт
    elif delta < -threshold:
        return "↓"  # падает
    return "→"  # стабильно
```

### 2.3 Подсветка таймаутов
```python
# В рендеринге строки
if not ok and h.get("total_pings", 0) > 2:
    # Мигание или специальный символ для повторяющихся таймаутов
    host_txt = f"❌ {hostname}"
```

### 2.4 Пример итоговой строки
```
# Компактный режим:
# ▂▄▆ 12ms ↓+5ms │ 45ms →+1ms │ ❌ 150ms ↑+20ms │ 67ms →-2ms

# Стандартный режим:
# #1  ▂▄▆  12ms ↓  +5ms  3ms jitter  5% loss  router.google.com
```

---

## Этап 3: Geolocation и ASN (4-5 часов)

### 3.1 Создать GeoService
```python
# services/geo_service.py
"""Geolocation service for IP addresses."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

@dataclass
class GeoInfo:
    country: str
    country_code: str
    city: str
    asn: str
    org: str  # Organization

class GeoService:
    """Service to lookup geolocation and ASN for IP addresses."""
    
    def __init__(self, cache_ttl: int = 3600) -> None:
        self._cache: dict[str, tuple[GeoInfo, float]] = {}
        self._cache_ttl = cache_ttl
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "pinger/2.0"})
    
    def get_geo(self, ip: str) -> Optional[GeoInfo]:
        """Get geolocation for IP with caching."""
        # Check cache
        if ip in self._cache:
            info, cached_at = self._cache[ip]
            if time.time() - cached_at < self._cache_ttl:
                return info
        
        try:
            # Use ip-api.com (бесплатный, 45 запросов/мин)
            resp = self._session.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,city,as,org"},
                timeout=5
            )
            data = resp.json()
            
            if data.get("status") != "success":
                return None
            
            info = GeoInfo(
                country=data.get("country", "?"),
                country_code=data.get("countryCode", ""),
                city=data.get("city", ""),
                asn=data.get("as", "").replace("AS", ""),
                org=data.get("org", ""),
            )
            
            self._cache[ip] = (info, time.time())
            return info
            
        except Exception as exc:
            logging.debug(f"Geo lookup failed for {ip}: {exc}")
            return None
```

### 3.2 Интеграция в HopMonitorService
```python
# services/hop_monitor_service.py
class HopMonitorService:
    def __init__(self, executor: ThreadPoolExecutor) -> None:
        # ... существующее ...
        self._geo_service: Optional[GeoService] = None
    
    def enable_geo(self) -> None:
        """Enable geolocation lookups."""
        if self._geo_service is None:
            from .geo_service import GeoService
            self._geo_service = GeoService()
    
    def _update_hop_geo(self, hop: HopStatus) -> None:
        """Update geolocation for hop (async, non-blocking)."""
        if self._geo_service is None:
            return
        
        # Запустить в фоне, не блокировать
        def _do_lookup():
            geo = self._geo_service.get_geo(hop.ip)
            if geo:
                hop.geo_info = geo
        
        # Небольшая задержка, чтобы не спамить API при старте
        threading.Timer(1.0, _do_lookup).start()
```

### 3.3 Обновить to_dict()
```python
def to_dict(self) -> Dict[str, Any]:
    return {
        # ... существующие поля ...
        "country": getattr(self, 'geo_info', None)?.country or "",
        "country_code": getattr(self, 'geo_info', None)?.country_code or "",
        "asn": getattr(self, 'geo_info', None)?.asn or "",
    }
```

### 3.4 UI для geolocation
```python
# В ui.py render_hop_panel
# Добавить колонку или отображать в расширенном режиме:
if tier == "wide":
    country = h.get("country_code", "")
    asn = h.get("asn", "")
    if country or asn:
        extra = f"[{_TEXT_DIM}][{country}]{' ' + asn if asn else ''}[/{_TEXT_DIM}]"
```

---

## Этап 4: Настраиваемые цветовые пороги (1-2 часа)

### 4.1 Добавить настройки в config/settings.py
```python
# Hop monitoring settings
HOP_LATENCY_GOOD = int(os.environ.get("HOP_LATENCY_GOOD", "50"))        # ms
HOP_LATENCY_MEDIUM = int(os.environ.get("HOP_LATENCY_MEDIUM", "150"))   # ms
HOP_LATENCY_BAD = int(os.environ.get("HOP_LATENCY_BAD", "300"))         # ms
HOP_LOSS_WARNING = float(os.environ.get("HOP_LOSS_WARNING", "5.0"))     # %
HOP_LOSS_CRITICAL = float(os.environ.get("HOP_LOSS_CRITICAL", "20.0"))  # %
HOP_JITTER_WARNING = float(os.environ.get("HOP_JITTER_WARNING", "20.0")) # ms

# UI settings
HOP_SPARKLINE_LENGTH = int(os.environ.get("HOP_SPARKLINE_LENGTH", "10"))
HOP_SHOW_GEO = os.environ.get("HOP_SHOW_GEO", "true").lower() in ("true", "1")
```

### 4.2 Обновить UI рендеринг
```python
# ui.py
from config import HOP_LATENCY_GOOD, HOP_LATENCY_MEDIUM, HOP_LATENCY_BAD

def _lat_color(self, latency: float) -> str:
    """Return color based on latency threshold."""
    if latency <= HOP_LATENCY_GOOD:
        return _GREEN
    elif latency <= HOP_LATENCY_MEDIUM:
        return _YELLOW
    elif latency <= HOP_LATENCY_BAD:
        return _ORANGE
    return _RED
```

---

## Файлы для изменения

| Файл | Изменения |
|------|-----------|
| `services/hop_monitor_service.py` | +jitter, +delta, +geo_service integration |
| `services/geo_service.py` | **NEW** — geolocation сервис |
| `services/__init__.py` | +GeoService, +GeoInfo |
| `config/settings.py` | +HOP_* настройки |
| `config/__init__.py` | экспорт новых настроек |
| `ui.py` | +спарклайны, +стрелки, +колонки |

---

## Оценка времени

| Этап | Время | Описание |
|-------|-------|----------|
| 1 | 2-3 ч | Базовые метрики (jitter, delta) |
| 2 | 3-4 ч | Визуальные улучшения |
| 3 | 4-5 ч | Geolocation + ASN |
| 4 | 1-2 ч | Настраиваемые пороги |
| **Итого** | **10-14 ч** | Полный набор улучшений |

---

## Примеры UI

### Компактный режим (текущий + улучшения)
```
┌─────────────────────────────────────────┐
│  ▶ HOP HEALTH                          │
├────┬─────────┬────────┬──────┬────────┤
│ #  │ Latency │  Trend │ Loss │ Host   │
├────┼─────────┼────────┼──────┼────────┤
│ 1  │  12ms   │ ▂▄▆↓+5 │  0%  │ local  │
│ 2  │  45ms   │ ▅▇→+1  │  0%  │ gw     │
│ 3  │ ❌150ms │ ▁❌↑�  │ 25%  │ isp    │
│ 4  │  67ms   │ ▃▅→-2  │  0%  │ core   │
└────┴─────────┴────────┴──────┴────────┘
```

### Стандартный/широкий режим
```
┌─────────────────────────────────────────────────────────────────────┐
│  ▶ HOP HEALTH                                    [#4 AS29134 LTE] │
├────┬──────┬───────┬──────┬──────┬───────┬─────────┬────────────────┤
│ #  │ Min   │  Avg  │ Last │ Δ    │ Jitter │ Loss    │ Host          │
├────┼──────┼───────┼──────┼──────┼───────┼─────────┼────────────────┤
│ 1  │  8ms  │ 12ms  │ 15ms │ +3ms │ 2.1ms  │  0.0%   │ 192.168.1.1   │
│ 2  │ 35ms  │ 45ms  │ 52ms │ +7ms │ 8.3ms  │  0.0%   │ [RU] AS12345  │
│ 3  │ --    │  --   │  ❌  │  --  │  --    │ 25.0%   │ [US] AS29134  │
└────┴──────┴───────┴──────┴──────┴───────┴─────────┴────────────────┘
```
