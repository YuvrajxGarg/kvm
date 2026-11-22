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
        from .winservice import service_main

        service_main()
        return
    if args and args[0] in ("service-install", "service-remove"):
        from . import winservice

        sys.exit(winservice.install_service() if args[0] == "service-install" else winservice.remove_service())
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
