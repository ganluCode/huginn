"""Huginn scheduler module.

Provides task scheduling capabilities for automated spider runs using APScheduler.
"""

from huginn.scheduler.cron import parse_cron

__all__ = ["parse_cron"]
