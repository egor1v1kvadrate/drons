"""Мелкие помощники для интерфейса менеджера, которые нужны сразу нескольким вкладкам."""
from tkinter import messagebox


def set_text(box, text: str):
    """Заменить весь текст в CTkTextbox, оставив его доступным только для чтения."""
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("end", text)
    box.configure(state="disabled")


def run_action(parent, action, success_message=None):
    """Выполнить действие и показать понятное сообщение.

    Убирает одинаковые try/except из каждой вкладки:
      ValueError   -> «ошибка ввода» (жёлтое предупреждение)
      другое       -> «ошибка» (красное окно)
    Возвращает результат действия или None, если была ошибка.
    """
    try:
        result = action()
    except ValueError as e:
        messagebox.showwarning("Ошибка ввода", str(e), parent=parent)
        return None
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось выполнить операцию: {e}", parent=parent)
        return None

    if success_message:
        messagebox.showinfo("Успех", success_message, parent=parent)
    return result
