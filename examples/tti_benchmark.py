from argparse import ArgumentParser

from devito.compiler import compiler_registry
from tti_example import run

try:
    from opescibench import Benchmark, Executor, Plotter
except:
    Benchmark = None
    Executor = None
    Plotter = None


if __name__ == "__main__":
    description = "Example script for TTI."
    parser = ArgumentParser(description=description)

    parser.add_argument(dest="execmode", nargs="?", default="run",
                        choices=["run", "bench", "plot"],
                        help="Script mode. Either 'run', 'bench' or 'plot'")
    parser.add_argument(dest="compiler", nargs="?", default="gnu",
                        choices=compiler_registry.keys())
    parser.add_argument("-o", "--omp", action="store_true",
                        help="Enable OpenMP")
    parser.add_argument("-d", "--dimensions", nargs=3, default=[50, 50, 50],
                        help="Dimension of the grid")
    parser.add_argument("-s", "--spacing", nargs=2, default=[20.0, 20.0],
                        help="Spacing on the grid")
    parser.add_argument("-t", "--tn", default=250,
                        type=int, help="Number of timesteps")
    parser.add_argument("-c", "--cse", action="store_true",
                        help=("Benchmark with CSE on and off. " +
                              "Enables CSE when execmode is run"))
    parser.add_argument("-a", "--auto_tuning", action="store_true",
                        help=("Benchmark with auto tuning on and off. " +
                              "Enables auto tuning when execmode is run"))
    parser.add_argument("-cb", "--cache_blocking", nargs=2, type=int,
                        default=None, help="Uses provided block sizes when AT is off")
    parser.add_argument("-r", "--resultsdir", default="results",
                        help="Directory containing results")
    parser.add_argument("-p", "--plotdir", default="plots",
                        help="Directory containing plots")
    parser.add_argument("--max_bw", type=float, help="Maximum bandwith of the system")
    parser.add_argument("--max_flops", type=float, help="Maximum FLOPS of the system")

    args = parser.parse_args()

    parameters = vars(args).copy()
    del parameters["execmode"]
    del parameters["resultsdir"]
    del parameters["plotdir"]
    del parameters["max_bw"]
    del parameters["max_flops"]
    del parameters["omp"]

    parameters["dimensions"] = tuple(parameters["dimensions"])
    parameters["spacing"] = tuple(parameters["spacing"])
    if parameters["cache_blocking"]:
        parameters["cache_blocking"] = parameters["cache_blocking"] + [None]
    parameters["compiler"] = compiler_registry[args.compiler](openmp=args.omp)

    if args.execmode == "run":
        run(**parameters)

    if args.execmode == "bench":
        if Benchmark is None:
            raise ImportError("Could not find opescibench utility package.\n"
                              "Please install from https://github.com/opesci/opescibench")

        if parameters["auto_tuning"]:
            parameters["auto_tuning"] = [True, False]

        if parameters["cse"]:
            parameters["cse"] = [True, False]

        class TTIExecutor(Executor):
            """Executor class that defines how to run TTI benchmark"""

            def run(self, *args, **kwargs):
                gflops, oi = run(*args, **kwargs)

                self.register(gflops["kernel"], measure="gflops")
                self.register(oi["kernel"], measure="oi")

        bench = Benchmark(name="TTI", resultsdir=args.resultsdir, parameters=parameters)
        bench.execute(TTIExecutor(), warmups=0)
        bench.save()

    if args.execmode == "plot":
        if parameters["auto_tuning"]:
            parameters["auto_tuning"] = [True, False]

        if parameters["cse"]:
            parameters["cse"] = [True, False]

        bench = Benchmark(name="TTI", resultsdir=args.resultsdir, parameters=parameters)
        bench.load()

        oi_dict = {}
        mflops_dict = {}

        gflops = bench.lookup(params=parameters, measure="gflops")
        oi = bench.lookup(params=parameters, measure="oi")

        for key, gflops in gflops.items():
            oi_value = oi[key]
            key = dict(key)
            label = "TTI, CSE: %s, AT: %s" % (key["cse"], key["auto_tuning"])
            mflops_dict[label] = gflops * 1000
            oi_dict[label] = oi_value

        name = "TTI - Dimensions: %s, Spacing: %s.pdf" % \
            (parameters["dimensions"], parameters["spacing"])

        plotter = Plotter()
        plotter.plot_roofline(
            name, mflops_dict, oi_dict, args.max_bw, args.max_flops)
