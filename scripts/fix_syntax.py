import os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 修复 f\"\"\" 错误
    new_content = content.replace('f\\\"\\\"\\\"', 'f"""')
    new_content = new_content.replace('\\\"\\\"\\\"', '"""')
    
    if content != new_content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {path}")

for root, dirs, files in os.walk('gui'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
