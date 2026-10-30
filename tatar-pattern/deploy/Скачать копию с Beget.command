#!/bin/zsh
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
/usr/bin/python3 "$SCRIPT_DIR/beget_daily_backup.py" --run
result=$?
print
if (( result == 0 )); then
  print 'Ежедневное обслуживание Beget и Mac завершено.'
else
  print "Проверка завершилась с кодом $result. Сохрани вывод для чата Beget."
fi
read 'reply?Нажми Enter, чтобы закрыть окно.'
exit "$result"
