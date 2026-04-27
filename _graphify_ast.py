import json, io
from graphify.extract import collect_files, extract
from pathlib import Path

detect = json.loads(Path('.graphify_detect.json').read_text())
code_files = []
for f in detect.get('files', {}).get('code', []):
    if Path(f).is_dir():
        code_files.extend(collect_files(Path(f)))
    else:
        code_files.append(Path(f))

print(f"Collected {len(code_files)} code files for AST extraction")

if code_files:
    result = extract(code_files)
    with io.open('.graphify_ast.json', 'w', encoding='utf-8') as out:
        json.dump(result, out, indent=2, default=str)
    nodes = len(result['nodes'])
    edges = len(result['edges'])
    print(f"AST: {nodes} nodes, {edges} edges")
else:
    with io.open('.graphify_ast.json', 'w', encoding='utf-8') as out:
        json.dump({'nodes': [], 'edges': [], 'input_tokens': 0, 'output_tokens': 0}, out, indent=2)
    print('No code files - skipping AST extraction')