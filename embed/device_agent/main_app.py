"""Backward-compatible launcher for the restructured runtime package."""

from runtime.main_app import AppConfig, MainApp


if __name__ == "__main__":
    app = MainApp(AppConfig(), use_mock_hardware=False, use_mock_camera=False)
    app.run()
