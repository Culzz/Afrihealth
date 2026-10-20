import traceback, sys
print("python:", sys.version)
try:
    sys.path.insert(0, ".")
    import services.api.app.main as m
    print("import OK:", type(m.app))
except Exception:
    traceback.print_exc()
