import re
tokens = ['fastapi', 'uvicorn[standard]', 'python-jose[cryptography]',
          'passlib[bcrypt]', 'sqlalchemy>=2.0', 'pydantic>=2.6',
          'A', 'modern', 'high-performance']
pattern = r"[a-zA-Z][a-zA-Z0-9_\-]+(\[\w+\])?([><=!~]{1,2}[\w\.\*]+)?"
for t in tokens:
    m = re.fullmatch(pattern, t)
    print("  {:<35} -> {}".format(repr(t), "MATCH" if m else "skip"))
