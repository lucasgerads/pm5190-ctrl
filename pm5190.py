#!/usr/bin/env python3
"""PM5190 LF synthesizer GPIB controller."""

import time
import serial
from textual.app import App, ComposeResult
from textual.screen import Screen
from textual.widgets import Header, Footer, Input, Button, Label, RadioSet, RadioButton
from textual.containers import Vertical
from textual import on

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD = 115200
DEFAULT_GPIB_ADDR = 4


def _range_i(vpp: float) -> int:
    return 0 if vpp < 0.2 else (1 if vpp < 2.0 else 2)


def _fmt_ac(vpp: float) -> str:
    """Format amplitude using same string-slice algorithm as PM5190 BASIC manual examples."""
    i = _range_i(vpp)
    s = f" {100.0005 + vpp:.4f}"
    return s[4 - i : 8 - i]


def _fmt_dc(dc: float, vpp: float) -> str:
    """Format DC offset; decimal position implied by amplitude range."""
    i = _range_i(vpp)
    sign = "-" if dc < 0 else ""
    s = f" {10.00005 + abs(dc) / 10:.5f}"
    return sign + s[6 - i : 8 - i]


def parse_freq(value: str) -> float:
    value = value.strip()
    suffixes = {"m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6}
    if value and value[-1] in suffixes:
        return float(value[:-1]) * suffixes[value[-1]]
    return float(value)


def build_command(freq_hz: float, vpp: float, dc: float, waveform: int) -> str:
    return f"F{freq_hz / 1000:g}A{_fmt_ac(vpp)}D{_fmt_dc(dc, vpp)}W{waveform}"


class PreferencesScreen(Screen):
    CSS = """
    Screen { align: center middle; }
    #prefs-panel {
        width: 54;
        border: solid $accent;
        padding: 1 2;
    }
    Label.field { margin-top: 1; }
    Button { margin-top: 1; width: 100%; }
    #cancel { margin-top: 0; }
    """

    BINDINGS = [("escape", "app.pop_screen", "Back"), ("ctrl+s", "save", "Save")]

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="prefs-panel"):
            yield Label("Serial Port", classes="field")
            yield Input(self.app.port, id="pref-port", placeholder="/dev/ttyUSB0")
            yield Label("Baud Rate", classes="field")
            yield Input(str(self.app.baud), id="pref-baud", placeholder="115200")
            yield Label("GPIB Address", classes="field")
            yield Input(str(self.app.gpib_addr), id="pref-addr", placeholder="0 – 30")
            yield Button("Save & Reconnect", id="save", variant="success")
            yield Button("Cancel", id="cancel", variant="default")
        yield Footer()

    def _save(self) -> None:
        try:
            self.app.port = self.query_one("#pref-port", Input).value.strip()
            self.app.baud = int(self.query_one("#pref-baud", Input).value)
            self.app.gpib_addr = int(self.query_one("#pref-addr", Input).value)
            self.app.pop_screen()
            self.app.reconnect()
        except ValueError:
            pass

    def action_save(self) -> None:
        self._save()

    @on(Button.Pressed, "#save")
    def on_save(self) -> None:
        self._save()

    @on(Button.Pressed, "#cancel")
    def on_cancel(self) -> None:
        self.app.pop_screen()


class PM5190App(App):
    CSS = """
    Screen { align: center middle; }
    #panel {
        width: 54;
        border: solid $success;
        padding: 1 2;
    }
    Label.field { margin-top: 1; }
    #status { height: 3; margin-top: 1; }
    Button { margin-top: 1; width: 100%; }
    """

    TITLE = "PM5190 Controller"
    BINDINGS = [("f2", "preferences", "Preferences"), ("ctrl+t", "send", "Transmit"), ("ctrl+q", "quit", "Quit")]

    def __init__(self) -> None:
        super().__init__()
        self.ser: serial.Serial | None = None
        self.port = DEFAULT_PORT
        self.baud = DEFAULT_BAUD
        self.gpib_addr = DEFAULT_GPIB_ADDR

    def on_mount(self) -> None:
        self.reconnect()

    def reconnect(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=1)
            time.sleep(2.0)  # wait for Arduino reset on connect
            self.ser.write(b"++ver\r\n")
            time.sleep(0.05)
            version = self.ser.readline().decode(errors="replace").strip()
            for cmd in (f"++mode 1", f"++addr {self.gpib_addr}", "++eos 3"):
                self.ser.write((cmd + "\r\n").encode())
                time.sleep(0.05)
            self._status(f"Port: {self.port}\nFirmware: {version}", "green")
        except serial.SerialException as e:
            self._status(f"Serial error: {e}", "red")

    def compose(self) -> ComposeResult:
        yield Header()
        with Vertical(id="panel"):
            yield Label("Frequency (Hz)", classes="field")
            yield Input("1000", id="freq", placeholder="0.001 – 2000000")
            yield Label("Amplitude Vpp", classes="field")
            yield Input("1.00", id="vpp", placeholder="0.001 – 19.9")
            yield Label("DC Offset (V)", classes="field")
            yield Input("0.00", id="dc", placeholder="-9.9 – 9.9")
            yield Label("Waveform", classes="field")
            with RadioSet(id="waveform"):
                yield RadioButton("Sine", value=True)
                yield RadioButton("Square")
                yield RadioButton("Triangle")
            yield Button("Send", id="send", variant="success")
            yield Label("", id="status")
        yield Footer()

    def _do_send(self) -> None:
        try:
            freq = parse_freq(self.query_one("#freq", Input).value)
            vpp = float(self.query_one("#vpp", Input).value)
            dc = float(self.query_one("#dc", Input).value)
            wf = self.query_one("#waveform", RadioSet).pressed_index + 1
            cmd = build_command(freq, vpp, dc, wf)
            if self.ser and self.ser.is_open:
                self.ser.write((cmd + "\x03\r\n").encode())
                self._status(f"Sent: {cmd}<ETX>", "green")
            else:
                self._status("Not connected", "red")
        except ValueError:
            self._status("Invalid input", "red")
        except serial.SerialException as e:
            self._status(f"Serial error: {e}", "red")

    @on(Button.Pressed, "#send")
    def on_send_pressed(self) -> None:
        self._do_send()

    def action_send(self) -> None:
        self._do_send()

    def action_preferences(self) -> None:
        self.push_screen(PreferencesScreen())

    def _status(self, msg: str, color: str = "white") -> None:
        self.query_one("#status", Label).update(f"[{color}]{msg}[/{color}]")

    def on_unmount(self) -> None:
        if self.ser:
            self.ser.close()


if __name__ == "__main__":
    PM5190App().run()
