"""Test Scrapy project structure setup (F-001)."""

from pathlib import Path

import pytest


class TestScrapyStructure:
    """Verify scrapy.cfg and package skeleton are properly created."""

    @pytest.fixture
    def project_root(self) -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent.parent

    def test_scrapy_cfg_exists(self, project_root: Path):
        """scrapy.cfg should exist with correct settings."""
        cfg_path = project_root / "scrapy.cfg"
        assert cfg_path.exists(), "scrapy.cfg must exist"

        content = cfg_path.read_text()
        assert "[settings]" in content, "scrapy.cfg must have [settings] section"
        assert "default = huginn.scrapy.settings" in content, "default must point to huginn.scrapy.settings"
        assert "[deploy]" in content, "scrapy.cfg must have [deploy] section"
        assert "project = huginn" in content, "deploy project must be huginn"

    def test_scrapy_package_exists(self, project_root: Path):
        """huginn/scrapy/ package should exist and be importable."""
        scrapy_path = project_root / "huginn" / "scrapy"
        init_path = scrapy_path / "__init__.py"

        assert scrapy_path.is_dir(), "huginn/scrapy/ directory must exist"
        assert init_path.exists(), "huginn/scrapy/__init__.py must exist"

    def test_scrapy_package_importable(self):
        """huginn.scrapy module should be importable."""
        import huginn.scrapy  # noqa: F401

    def test_spiders_package_exists(self, project_root: Path):
        """huginn/scrapy/spiders/ package should exist and be importable."""
        spiders_path = project_root / "huginn" / "scrapy" / "spiders"
        init_path = spiders_path / "__init__.py"

        assert spiders_path.is_dir(), "huginn/scrapy/spiders/ directory must exist"
        assert init_path.exists(), "huginn/scrapy/spiders/__init__.py must exist"

    def test_spiders_package_importable(self):
        """huginn.scrapy.spiders module should be importable."""
        import huginn.scrapy.spiders  # noqa: F401

    def test_test_scrapy_package_exists(self, project_root: Path):
        """tests/test_scrapy/ package should exist."""
        test_scrapy_path = project_root / "tests" / "test_scrapy"
        init_path = test_scrapy_path / "__init__.py"

        assert test_scrapy_path.is_dir(), "tests/test_scrapy/ directory must exist"
        assert init_path.exists(), "tests/test_scrapy/__init__.py must exist"
