"""Spectral representation of the light flowing along system-graph edges.

All quantities are SI: wavelengths in meters, powers in watts. An
`OpticalSignal` is a sparse list of spectral channels — pump lines, signal
lines, and ASE bins — that solvers consume and produce as light moves through
the assembled laser system.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Literal

ChannelKind = Literal["pump", "signal", "ase"]


@dataclass(frozen=True)
class SpectralChannel:
    """One spectral line or bin.

    Attributes:
        wavelength: center wavelength (m).
        power: optical power (W).
        kind: 'pump' | 'signal' | 'ase'.
        width: spectral bin width (m); 0 for laser/pump lines.
    """
    wavelength: float
    power: float
    kind: ChannelKind
    width: float = 0.0

    def scaled(self, factor: float) -> "SpectralChannel":
        return replace(self, power=max(self.power * factor, 0.0))


@dataclass
class OpticalSignal:
    """The full optical field crossing a point of the circuit (forward direction)."""
    channels: list[SpectralChannel] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------
    @classmethod
    def empty(cls) -> "OpticalSignal":
        return cls([])

    @classmethod
    def line(cls, wavelength: float, power: float, kind: ChannelKind = "signal") -> "OpticalSignal":
        return cls([SpectralChannel(wavelength, power, kind)])

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------
    def total_power(self) -> float:
        return float(sum(ch.power for ch in self.channels))

    def power_of_kind(self, kind: ChannelKind) -> float:
        return float(sum(ch.power for ch in self.channels if ch.kind == kind))

    def power_in_band(self, wl_min: float, wl_max: float) -> float:
        return float(
            sum(ch.power for ch in self.channels if wl_min <= ch.wavelength <= wl_max)
        )

    def pumps(self) -> list[SpectralChannel]:
        return [ch for ch in self.channels if ch.kind == "pump"]

    def signals(self) -> list[SpectralChannel]:
        return [ch for ch in self.channels if ch.kind == "signal"]

    def ase(self) -> list[SpectralChannel]:
        return [ch for ch in self.channels if ch.kind == "ase"]

    # ------------------------------------------------------------------
    # Transformations (all return new instances)
    # ------------------------------------------------------------------
    def attenuated_db(self, loss_db: float) -> "OpticalSignal":
        """Apply a flat insertion loss in dB to every channel."""
        factor = 10.0 ** (-loss_db / 10.0)
        return OpticalSignal([ch.scaled(factor) for ch in self.channels])

    def filtered(self, transmission: Callable[[float], float]) -> "OpticalSignal":
        """Apply a wavelength-dependent power transmission T(lambda) in [0, 1]."""
        out = []
        for ch in self.channels:
            t = min(max(float(transmission(ch.wavelength)), 0.0), 1.0)
            if ch.power * t > 0.0:
                out.append(ch.scaled(t))
        return OpticalSignal(out)

    def merged(self, other: "OpticalSignal") -> "OpticalSignal":
        """Combine two signals (e.g. WDM ports); coincident lines are summed."""
        combined: dict[tuple[float, str], SpectralChannel] = {}
        for ch in list(self.channels) + list(other.channels):
            key = (round(ch.wavelength, 15), ch.kind)
            if key in combined:
                prev = combined[key]
                combined[key] = replace(prev, power=prev.power + ch.power)
            else:
                combined[key] = ch
        return OpticalSignal(sorted(combined.values(), key=lambda c: c.wavelength))

    def without_kind(self, kind: ChannelKind) -> "OpticalSignal":
        return OpticalSignal([ch for ch in self.channels if ch.kind != kind])

    def dropped_below(self, min_power: float = 1e-12) -> "OpticalSignal":
        """Prune numerically negligible channels."""
        return OpticalSignal([ch for ch in self.channels if ch.power >= min_power])

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "wavelengths_nm": [ch.wavelength * 1e9 for ch in self.channels],
            "powers_w": [ch.power for ch in self.channels],
            "kinds": [ch.kind for ch in self.channels],
            "widths_nm": [ch.width * 1e9 for ch in self.channels],
            "total_power_w": self.total_power(),
        }

    @classmethod
    def from_channels(cls, channels: Iterable[SpectralChannel]) -> "OpticalSignal":
        return cls(sorted(channels, key=lambda c: c.wavelength))
