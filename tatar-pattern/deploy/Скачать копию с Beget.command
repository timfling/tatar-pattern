#!/bin/zsh
SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
/usr/bin/python3 "$SCRIPT_DIR/mac_manual_backup.py"
result=$?
print
if (( result == 0 )); then
  print 'Проверенная резервная копия на Mac готова.'
else
  print "Проверка завершилась с кодом $result. Сохрани вывод для чата Beget."
fi
read 'reply?Нажми Enter, чтобы закрыть окно.'
exit "$result"
