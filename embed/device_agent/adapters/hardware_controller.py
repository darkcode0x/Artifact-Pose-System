"""Dieu khien Pan-Tilt (PCA9685) va Slider (Stepper qua GPIO)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServoConfig:
    """Cau hinh servo cho PCA9685."""

    pan_channel: int = 0
    tilt_channel: int = 1
    pan_min: int = 0
    pan_max: int = 180
    tilt_min: int = 0
    tilt_max: int = 120


@dataclass
class SliderConfig:
    """Cau hinh stepper slider."""

    x_pul_pin: int = 17
    x_dir_pin: int = 27
    z_pul_pin: int = 22
    z_dir_pin: int = 23
    microstep: int = 32
    pulse_delay: float = 0.0005


class HardwareController:
    """Controller tong hop cho servo pan-tilt va slider X/Z."""

    def __init__(
        self,
        servo_config: Optional[ServoConfig] = None,
        slider_config: Optional[SliderConfig] = None,
    ) -> None:
        self.servo_config = servo_config or ServoConfig()
        self.slider_config = slider_config or SliderConfig()

        self.current_yaw: int = 110
        self.current_pitch: int = 50
        self.current_x_steps: int = 0
        self.current_z_steps: int = 0

        self._kit = None
        self._gpio = None

        self._init_servo_driver()
        self._init_stepper_driver()

    def _init_servo_driver(self) -> None:
        """Khoi tao PCA9685 qua ServoKit."""
        try:
            from adafruit_servokit import ServoKit

            self._kit = ServoKit(channels=16)
        except Exception as exc:
            print(f"[HW] Loi ket noi PCA9685/I2C: {exc}")
            raise

    def _init_stepper_driver(self) -> None:
        """Khoi tao GPIO cho stepper slider."""
        try:
            import RPi.GPIO as GPIO

            self._gpio = GPIO
            self._gpio.setmode(GPIO.BCM)
            self._gpio.setup(
                [
                    self.slider_config.x_pul_pin,
                    self.slider_config.x_dir_pin,
                    self.slider_config.z_pul_pin,
                    self.slider_config.z_dir_pin,
                ],
                GPIO.OUT,
            )
        except Exception as exc:
            print(f"[HW] Loi khoi tao GPIO stepper: {exc}")
            raise

    def set_pan_tilt(self, yaw_deg: float, pitch_deg: float) -> None:
        """Dat truc tiep goc Yaw/Pitch nhan duoc tu lenh."""
        if self._kit is None:
            raise RuntimeError("PCA9685 chua duoc khoi tao")

        try:
            pan_target = int(round(yaw_deg))
            pan_target = max(self.servo_config.pan_min, min(self.servo_config.pan_max, pan_target))
            print(f"pan_target: {pan_target}")
            tilt_target = int(round(pitch_deg))
            tilt_target = max(self.servo_config.tilt_min, min(self.servo_config.tilt_max, tilt_target))
            print(f"tilt_target: {tilt_target}")
            self._kit.servo[self.servo_config.pan_channel].angle = pan_target
            self._kit.servo[self.servo_config.tilt_channel].angle = tilt_target
            self.current_yaw = pan_target
            self.current_pitch = tilt_target
        except Exception as exc:
            raise RuntimeError(f"Loi dieu khien servo: {exc}") from exc

    def move_slider_x(self, steps: int, direction: int) -> None:
        """Tinh tien slider truc X voi so buoc cho truoc."""
        self._run_stepper_axis(
            steps=steps,
            direction=direction,
            pul_pin=self.slider_config.x_pul_pin,
            dir_pin=self.slider_config.x_dir_pin,
            pulse_delay=None,
        )
        self.current_x_steps += steps if direction > 0 else -steps

    def move_slider_z(self, steps: int, direction: int) -> None:
        """Tinh tien slider truc Z (ho tro bo sung theo context du an)."""
        self._run_stepper_axis(
            steps=steps,
            direction=direction,
            pul_pin=self.slider_config.z_pul_pin,
            dir_pin=self.slider_config.z_dir_pin,
            pulse_delay=None,
        )
        self.current_z_steps += steps if direction > 0 else -steps

    def move_slider_x_with_delay(self, steps: int, direction: int, pulse_delay: float) -> None:
        """Tinh tien slider truc X voi pulse_delay override cho profile toc do."""
        self._run_stepper_axis(
            steps=steps,
            direction=direction,
            pul_pin=self.slider_config.x_pul_pin,
            dir_pin=self.slider_config.x_dir_pin,
            pulse_delay=pulse_delay,
        )
        self.current_x_steps += steps if direction > 0 else -steps

    def move_slider_z_with_delay(self, steps: int, direction: int, pulse_delay: float) -> None:
        """Tinh tien slider truc Z voi pulse_delay override cho profile toc do."""
        self._run_stepper_axis(
            steps=steps,
            direction=direction,
            pul_pin=self.slider_config.z_pul_pin,
            dir_pin=self.slider_config.z_dir_pin,
            pulse_delay=pulse_delay,
        )
        self.current_z_steps += steps if direction > 0 else -steps

    def reset_position(self) -> None:
        """Dua camera va slider ve moc mac dinh (0 do, 0 buoc)."""
        self.set_pan_tilt(0.0, 0.0)

        if self.current_x_steps != 0:
            direction_x = -1 if self.current_x_steps > 0 else 1
            self.move_slider_x(abs(self.current_x_steps), direction_x)

        if self.current_z_steps != 0:
            direction_z = -1 if self.current_z_steps > 0 else 1
            self.move_slider_z(abs(self.current_z_steps), direction_z)

    def cleanup(self) -> None:
        """Giai phong tai nguyen phan cung."""
        if self._gpio is not None:
            self._gpio.cleanup()

    def _run_stepper_axis(
        self,
        steps: int,
        direction: int,
        pul_pin: int,
        dir_pin: int,
        pulse_delay: Optional[float],
    ) -> None:
        """Phat xung stepper cho 1 truc."""
        if steps <= 0:
            return

        effective_pulse_delay = (
            pulse_delay if pulse_delay is not None else self.slider_config.pulse_delay
        )
        if effective_pulse_delay <= 0:
            effective_pulse_delay = self.slider_config.pulse_delay

        if self._gpio is None:
            raise RuntimeError("GPIO chua duoc khoi tao")

        gpio_direction = self._gpio.HIGH if direction > 0 else self._gpio.LOW
        self._gpio.output(dir_pin, gpio_direction)

        for _ in range(steps):
            self._gpio.output(pul_pin, self._gpio.HIGH)
            time.sleep(effective_pulse_delay)
            self._gpio.output(pul_pin, self._gpio.LOW)
            time.sleep(effective_pulse_delay)

