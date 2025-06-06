# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Dependency Management
- **Install dependencies**: `rye sync` (installs both main and dev dependencies)
- **Add new dependency**: `rye add <package-name>`
- **Add dev dependency**: `rye add --dev <package-name>`
- **Update lockfiles**: `rye lock`

### Testing
- **Run all tests**: `rye run pytest` or `pytest`
- **Run single test**: `pytest tests/test_specific.py::test_function`
- **Run with coverage**: Tests automatically generate HTML coverage reports in `tests/evidence/coverage/`
- **Test output**: HTML test reports generated in `tests/evidence/index.htm`

### Code Quality
- **Format code**: `rye fmt`
- **Lint code**: `rye lint`

### Building
- **Build package**: `rye build`

## Architecture Overview

This is a personal utility library focused on IoT, automation, and data collection applications, particularly for Raspberry Pi environments.

### Core Module Structure

#### Sensor Management (`src/my_lib/sensor/`)
- 19+ hardware sensor drivers with standardized interfaces
- I2C bus management and GPIO integration
- Environmental, analog, and specialized sensor support
- Object-oriented design with consistent error handling

#### Data Pipeline (`src/my_lib/sensor_data.py`)
- InfluxDB time-series database integration
- Complex Flux query generation for data aggregation
- Time-windowed analysis and equipment monitoring
- Handles sensor data validation and error recovery

#### Notification System (`src/my_lib/notify/`)
- Unified interface for Slack, LINE, and email notifications
- Rate limiting and footprint-based throttling
- Rich formatting and template support

#### Web Framework (`src/my_lib/webapp/`)
- Flask-based utilities for dashboards and APIs
- Configuration management with YAML + JSON schema validation
- Event handling, logging, and request compression

#### Web Automation (`src/my_lib/store/`, `selenium_util.py`)
- E-commerce scraping (Amazon, Mercari) with CAPTCHA handling
- Template-driven automation with Selenium WebDriver
- Chrome profile management for persistent sessions

### Key Patterns

#### Configuration-Driven Design
- Centralized YAML configuration (`config.py`) with schema validation
- Environment variable integration for sensitive data
- Modular configuration sections for different subsystems

#### Hardware Integration
- Deep I2C sensor integration with SMBus2
- Raspberry Pi GPIO utilities (`rpi.py`)
- Serial communication support

#### Production Features
- Health check endpoints (`healthz.py`)
- Structured logging with compression (`logger.py`)
- Thread-safe operations and process management
- Data compression and caching

### Testing Setup
- Pytest with comprehensive coverage reporting
- Playwright integration for web testing (see `conftest.py`)
- Test evidence collection with video recording
- Custom fixtures for host/port configuration

### Development Notes
- Uses Rye for modern Python dependency management
- InfluxDB required for sensor data functionality
- Selenium Chrome profiles stored in `tests/data/chrome/`
- Configuration examples in `tests/data/config.yaml`
