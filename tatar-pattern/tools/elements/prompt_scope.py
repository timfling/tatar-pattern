"""Shared wording that pins a generation prompt to the selected motif boundary."""
from __future__ import annotations


def selection_instruction(record: dict[str, str]) -> str:
    """Describe the target extent without broadening it to neighboring ornament."""
    description = record["description"].strip()
    motif_class = record["motif_class"].strip()
    lower_class = motif_class.lower()
    parts = [
        f"Выдели только один описанный самостоятельный элемент: «{description}» (класс: {motif_class}).",
        "Проведи границу по внешнему видимому контуру этого элемента. Включай только его соединённые части, названные в описании; отдельные соседние цветы, листья, завитки, полосы каймы и фон предмета исключай, даже если они попали в вырезку.",
    ]

    if any(word in lower_class for word in ("бордюр", "кайма", "цепь", "полоса")):
        parts.append(
            "Если это повторяющийся ряд или полоса, сохрани ровно видимый отрезок с исходными концами; не добавляй повторов и не достраивай продолжение за краями вырезки."
        )
    if "угол" in lower_class:
        parts.append(
            "Сохрани форму одного угла; не разворачивай его в полную рамку, квадратное панно или симметричную композицию."
        )
    if record.get("processing_note", "").strip():
        parts.append("Точная область и исключения для этого элемента: " + record["processing_note"].strip())

    return " ".join(parts)
