"""CLI entry point for huginn.playwright.runner.

This module enables running the Playwright runner as a module:
    python -m huginn.playwright.runner <flow_name>
    python -m huginn.playwright.runner --list
    python -m huginn.playwright.runner --help
"""

from huginn.playwright.runner import main

if __name__ == "__main__":
    main()
