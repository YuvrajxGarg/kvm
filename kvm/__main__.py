import os
import sys


def run():
    # A windowed build (no console) has no stdout/stderr; give the CLI somewhere to write.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w")
    args = [a for a in sys.argv[1:] if not a.startswith("-psn")]
    if args and args[0] == "service-run":
        from .winservice import service_log_path, service_main

        try:  # anything the service prints (a crash on import, say) lands in its log
            os.makedirs(os.path.dirname(service_log_path()), exist_ok=True)
            sys.stderr = sys.stdout = open(service_log_path(), "a", encoding="utf-8", buffering=1)
        except OSError:
            pass
        service_main()
        return
    if args and args[0] in ("service-install", "service-remove"):
        from . import winservice

        try:
            sys.exit(winservice.install_service() if args[0] == "service-install" else winservice.remove_service())
        except Exception:
            import traceback
            winservice.slog("%s failed:\n%s" % (args[0], traceback.format_exc()))
            sys.exit(1)
    if args and args[0] == "helper":
        from .winservice import helper_main

        helper_main()
        return
    if args and args[0] != "--background":
        from .cli import main

        sys.exit(main(args))
    try:
        from .webapp import main
    except ImportError as e:
        print("The window needs pywebview: pip install -r requirements.txt (%s)" % e)
        print("Or run without a window: python Kvm.py run")
        sys.exit(1)
    main(background="--background" in args)


if __name__ == "__main__":
    run()
