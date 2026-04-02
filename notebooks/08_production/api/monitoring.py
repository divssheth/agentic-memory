"""
Monitoring and telemetry setup for production.
"""

import os
import time
from contextlib import contextmanager
from functools import wraps
from typing import Optional
import structlog

from .config import settings


# ==================== Structured Logging ====================

def setup_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level="INFO"),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True
    )


logger = structlog.get_logger()


# ==================== Application Insights ====================

_telemetry_client = None


def get_telemetry_client():
    """Get or create Application Insights telemetry client."""
    global _telemetry_client
    
    if _telemetry_client is None and settings.APPLICATIONINSIGHTS_CONNECTION_STRING:
        try:
            from opencensus.ext.azure.trace_exporter import AzureExporter
            from opencensus.ext.azure.log_exporter import AzureLogHandler
            from opencensus.trace import Tracer
            from opencensus.trace.samplers import ProbabilitySampler
            
            _telemetry_client = {
                "tracer": Tracer(
                    exporter=AzureExporter(
                        connection_string=settings.APPLICATIONINSIGHTS_CONNECTION_STRING
                    ),
                    sampler=ProbabilitySampler(1.0)
                ),
                "connection_string": settings.APPLICATIONINSIGHTS_CONNECTION_STRING
            }
        except ImportError:
            logger.warning("Application Insights packages not installed")
            _telemetry_client = {}
    
    return _telemetry_client or {}


def setup_monitoring():
    """Initialize all monitoring components."""
    setup_logging()
    get_telemetry_client()
    logger.info("monitoring_initialized", app_insights_enabled=bool(settings.APPLICATIONINSIGHTS_CONNECTION_STRING))


# ==================== Request Tracking ====================

@contextmanager
def track_request(operation_name: str, properties: dict = None):
    """
    Context manager for tracking request metrics.
    
    Usage:
        with track_request("create_travel_request"):
            # ... do work ...
    """
    start_time = time.time()
    success = True
    error = None
    
    try:
        yield
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        duration_ms = (time.time() - start_time) * 1000
        
        # Log structured data
        logger.info(
            "request_completed",
            operation=operation_name,
            duration_ms=round(duration_ms, 2),
            success=success,
            error=error,
            **(properties or {})
        )
        
        # Track in Application Insights
        tc = get_telemetry_client()
        if tc and "tracer" in tc:
            tracer = tc["tracer"]
            with tracer.span(name=operation_name) as span:
                span.add_attribute("duration_ms", duration_ms)
                span.add_attribute("success", success)
                if error:
                    span.add_attribute("error", error)


# ==================== Custom Metrics ====================

def track_memory_operation(operation: str, duration_ms: float, success: bool, details: dict = None):
    """Track memory service operations."""
    logger.info(
        "memory_operation",
        operation=operation,
        duration_ms=round(duration_ms, 2),
        success=success,
        **(details or {})
    )


def track_llm_call(model: str, duration_ms: float, tokens_used: int = None, success: bool = True):
    """Track LLM API calls."""
    logger.info(
        "llm_call",
        model=model,
        duration_ms=round(duration_ms, 2),
        tokens_used=tokens_used,
        success=success
    )


def track_approval_event(request_id: str, action: str, approver: str = None):
    """Track approval workflow events."""
    logger.info(
        "approval_event",
        request_id=request_id,
        action=action,
        approver=approver
    )


# ==================== Health Metrics ====================

class HealthMetrics:
    """Collect and report health metrics."""
    
    def __init__(self):
        self.request_count = 0
        self.error_count = 0
        self.last_request_time = None
    
    def record_request(self, success: bool):
        """Record a request."""
        self.request_count += 1
        if not success:
            self.error_count += 1
        self.last_request_time = time.time()
    
    def get_health_status(self) -> dict:
        """Get current health status."""
        error_rate = (self.error_count / self.request_count * 100) if self.request_count > 0 else 0
        
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "error_rate_percent": round(error_rate, 2),
            "last_request_time": self.last_request_time,
            "healthy": error_rate < 5  # Less than 5% error rate
        }


health_metrics = HealthMetrics()
