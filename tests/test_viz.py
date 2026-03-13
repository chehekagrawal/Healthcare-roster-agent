import pandas as pd
from visualizations import plot_market_trend

# Load data just like your app will
df_market = pd.read_csv("data/aggregated_operational_metrics.csv")
# Generate the chart object
fig = plot_market_trend(df_market, "CA") 
# Show it (this will open a browser window)
fig.show()