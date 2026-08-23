export interface PlotlyTrace {
  x: string[];
  y: Array<number | null>;
  name: string;
  type: "scatter";
  mode: "lines+markers";
  connectgaps: boolean;
  customdata: string[];
  hovertemplate: string;
}

export interface PlotlyApi {
  react(
    element: HTMLElement,
    traces: PlotlyTrace[],
    layout: Record<string, unknown>,
    config: Record<string, unknown>,
  ): Promise<void> | void;
  purge(element: HTMLElement): void;
}

declare global {
  interface Window {
    Plotly?: PlotlyApi;
  }
}

let plotlyLoadPromise: Promise<PlotlyApi> | null = null;

export function loadPlotly(): Promise<PlotlyApi> {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (plotlyLoadPromise) return plotlyLoadPromise;

  plotlyLoadPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/assets/plotly.min.js";
    script.async = true;
    script.dataset.plotlyLoader = "run-results";
    script.addEventListener(
      "load",
      () => {
        if (window.Plotly) resolve(window.Plotly);
        else reject(new Error("Plotly bundle did not initialize"));
      },
      { once: true },
    );
    script.addEventListener(
      "error",
      () => reject(new Error("Plotly bundle could not be loaded")),
      { once: true },
    );
    document.head.appendChild(script);
  });
  return plotlyLoadPromise;
}
