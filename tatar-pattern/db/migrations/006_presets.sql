-- Production presets only; no elements, users or fake generations.
INSERT INTO palettes(code,name,colors) VALUES
('emerald','Казанский изумруд','{"bg":"#123f34","ink":"#f2e5ca","gold":"#c99a4a","red":"#9d302b","blue":"#1f5069"}'),
('porcelain','Фарфор и киноварь','{"bg":"#efe7d7","ink":"#172b34","gold":"#bb8740","red":"#a33635","blue":"#1d4f68"}'),
('leather','Казанская кожа','{"bg":"#3b251a","ink":"#f1dec0","gold":"#d2a15d","red":"#7f2c24","blue":"#455e64"}')
ON CONFLICT(code) DO NOTHING;
INSERT INTO composition_schemes(code,name,scheme_type,rules) VALUES
('medallion','Медальон','медальон','{"rays":8}'),
('border','Бордюр','бордюр','{"repeat_count":6}'),
('rapport','Раппорт','раппорт','{"repeats":4}')
ON CONFLICT(code) DO NOTHING;
