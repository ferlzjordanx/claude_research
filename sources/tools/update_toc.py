import os, subprocess, sys, time, tempfile
sys.path.insert(0, [p for p in __import__('glob').glob('/root/.claude/skills/synced/*/docx/scripts')][0])
from office.soffice import get_soffice_env
import uno
from com.sun.star.beans import PropertyValue

src, dst = map(os.path.abspath, sys.argv[1:3])
prof = tempfile.mkdtemp()
env = get_soffice_env()
p = subprocess.Popen(["soffice", "--headless", "--invisible", "--nologo", "--norestore",
                      f"-env:UserInstallation=file://{prof}", "--accept=pipe,name=tocpipe;urp;"], env=env)
ctx = None
for _ in range(60):
    try:
        local = uno.getComponentContext()
        resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
        ctx = resolver.resolve("uno:pipe,name=tocpipe;urp;StarOffice.ComponentContext")
        break
    except Exception:
        time.sleep(1)
smgr = ctx.ServiceManager
desktop = smgr.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
def pv(n, v):
    x = PropertyValue(); x.Name = n; x.Value = v; return x
doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(src), "_blank", 0, (pv("Hidden", True),))
idx = doc.getDocumentIndexes()
for i in range(idx.getCount()):
    idx.getByIndex(i).update()
doc.storeToURL(uno.systemPathToFileUrl(dst), (pv("FilterName", "MS Word 2007 XML"),))
doc.close(True)
try: desktop.terminate()
except Exception: pass
p.wait(timeout=30)
print("updated", idx.getCount(), "index(es)")
