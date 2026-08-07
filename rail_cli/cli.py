"""CLI entry point — argparse subcommands for all RailGo APIs."""
import argparse
import datetime
import json
import sys

from rail_cli import __version__
from rail_cli.client import RailGoClient


def setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rail",
        description="RailGo data service CLI — query Chinese railway information.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="print request URL + status")
    parser.add_argument("--pretty", action="store_true", help="human-readable JSON output")
    parser.add_argument("--raw", action="store_true", help="print raw API response (unwrap nothing)")
    sub = parser.add_subparsers(dest="command", required=False)

    # Global flags also accepted after the subcommand (argparse parent parser trick).
    # default=SUPPRESS: if the flag is not given on the subcommand, don't override
    # the value parsed at the top level (e.g. `rail -v lucky` keeps verbose=True).
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true", default=argparse.SUPPRESS,
                        help="print request URL + status")
    common.add_argument("--pretty", action="store_true", default=argparse.SUPPRESS,
                        help="human-readable JSON output")
    common.add_argument("--raw", action="store_true", default=argparse.SUPPRESS,
                        help="print raw API response (unwrap nothing)")

    # --- misc ---
    sub.add_parser("version", help="show version")

    # --- train (V1) ---
    train_p = sub.add_parser("train", help="train-related queries (V1)", parents=[common])
    train_sub = train_p.add_subparsers(dest="train_cmd")

    train_q = train_sub.add_parser("query", help="query train by number", parents=[common])
    train_q.add_argument("train", help="train number, e.g. G1")

    train_s = train_sub.add_parser("sts", help="station-to-station train query", parents=[common])
    train_s.add_argument("from_", metavar="FROM", help="departure station telecode, e.g. SZQ")
    train_s.add_argument("to", metavar="TO", help="arrival station telecode, e.g. GGQ")
    train_s.add_argument("--date", default=None,
                         help="date YYYYMMDD or YYYY-MM-DD (default: today)")

    train_pres = train_sub.add_parser("preselect", help="train number autocomplete", parents=[common])
    train_pres.add_argument("keyword", help="search keyword, e.g. G1")

    # --- station (V1) ---
    sta_p = sub.add_parser("station", help="station-related queries (V1)", parents=[common])
    sta_sub = sta_p.add_subparsers(dest="station_cmd")

    sta_q = sta_sub.add_parser("query", help="query station by telecode", parents=[common])
    sta_q.add_argument("telecode", help="station telecode, e.g. XBG")

    sta_pres = sta_sub.add_parser("preselect", help="station name autocomplete", parents=[common])
    sta_pres.add_argument("keyword", help="search keyword, e.g. 新余")

    # --- lucky (V1) ---
    sub.add_parser("lucky", help="random train (memorial ticket)", parents=[common])

    # --- exit (V2) ---
    ex_p = sub.add_parser("exit", help="gate/platform/exit info (V2)", parents=[common])
    ex_p.add_argument("train", help="train number, e.g. G1")
    ex_p.add_argument("station", help="station telecode, e.g. VNP")
    ex_p.add_argument("--date", default=None, help="date (default: today)")
    ex_p.add_argument("--kind", default=None, choices=["arrival", "departure"],
                      help="arrival or departure (default: departure)")

    # --- delay (V2) ---
    del_p = sub.add_parser("delay", help="train delay status (V2)", parents=[common])
    del_p.add_argument("train", help="train number, e.g. G1")

    # --- screen (V2) ---
    sc_p = sub.add_parser("screen", help="station big screen (V2)", parents=[common])
    sc_p.add_argument("station", help="station telecode, e.g. BJP")
    sc_p.add_argument("--kind", default=None, choices=["departure", "arrival"],
                      help="departure or arrival (default: departure)")

    # --- main (V2) ---
    mn_p = sub.add_parser("main", help="train master data (V2)", parents=[common])
    mn_p.add_argument("train", help="train number, e.g. G1")
    mn_p.add_argument("--date", default=None, help="date YYYY-MM-DD or YYYYMMDD (default: today)")

    # --- coach (V2) ---
    co_p = sub.add_parser("coach", help="coach/car image info (V2)", parents=[common])
    co_p.add_argument("train", help="train number, e.g. G1")

    # --- map (V2) ---
    mp_p = sub.add_parser("map", help="train route line points (V2)", parents=[common])
    mp_p.add_argument("train", nargs="?", default=None, help="train number (optional)")

    return parser


def output(data, args) -> None:
    """Print data to stdout. With --pretty, pretty-print JSON."""
    if isinstance(data, str):
        print(data)
    elif args.pretty:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        json.dump(data, sys.stdout, ensure_ascii=False)
        print()


def main() -> None:
    parser = setup_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "version":
        print(f"rail {__version__}")
        return

    client = RailGoClient(verbose=args.verbose)

    try:
        if args.command == "train":
            sub = getattr(args, "train_cmd", None)
            if sub == "query":
                data = client.get_v1("/api/train/query", {"train": args.train})
            elif sub == "sts":
                date = args.date or datetime.date.today().strftime("%Y%m%d")
                data = client.get_v1("/api/train/sts_query",
                                     {"from": args.from_, "to": args.to, "date": date})
            elif sub == "preselect":
                data = client.get_v1("/api/train/preselect", {"keyword": args.keyword})
            else:
                parser.error("train requires a subcommand: query | sts | preselect")

        elif args.command == "station":
            sub = getattr(args, "station_cmd", None)
            if sub == "query":
                data = client.get_v1("/api/station/query", {"telecode": args.telecode})
            elif sub == "preselect":
                data = client.get_v1("/api/station/preselect", {"keyword": args.keyword})
            else:
                parser.error("station requires a subcommand: query | preselect")

        elif args.command == "lucky":
            data = client.get_v1("/api/lucky")

        elif args.command == "exit":
            data = client.get_v2("/api/v2/getExit", {
                "trainNum": args.train, "stationTelecode": args.station,
                "date": args.date, "kind": args.kind,
            }, raw=args.raw)

        elif args.command == "delay":
            data = client.get_v2("/api/v2/getTrainDelayAll", {"trainNum": args.train},
                                 raw=args.raw)

        elif args.command == "screen":
            data = client.get_v2("/api/v2/getStationBigScreen",
                                 {"stationTelecode": args.station, "kind": args.kind},
                                 raw=args.raw)

        elif args.command == "main":
            data = client.get_v2("/api/v2/getTrainMain",
                                 {"trainNum": args.train, "date": args.date},
                                 raw=args.raw)

        elif args.command == "coach":
            data = client.get_v2("/api/v2/getCoachPic", {"train": args.train}, raw=args.raw)

        elif args.command == "map":
            data = client.get_v2("/api/v2/mapLine", {"train": args.train}, raw=args.raw)

        else:
            parser.print_help()
            sys.exit(1)

        output(data, args)

    except RuntimeError as e:
        print(f"rail: error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
