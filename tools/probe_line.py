"""The engine test: Mika's first line (SP06) in Russian."""
import cyrfont

LINES = {
    0x3B20 - 0x3800: cyrfont.encode("Добро пожаловать в штаб ДЖАНКЕРа.￥Чем могу помочь?"),
}
