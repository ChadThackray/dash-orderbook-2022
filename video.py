
from dash import Dash, html, dcc, Input, Output, dash_table
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from decimal import Decimal
import pandas as pd
import requests
import math

app = Dash(external_stylesheets=[dbc.themes.CYBORG])

def dropdown_option(title, options, default_value, _id):

    return html.Div(children = [
        html.H2(title),
        dcc.Dropdown(options = options, value = default_value, id=_id)
        ])

app.layout = html.Div(children = [

    html.Div(children = [
        html.Div(children = [
            dash_table.DataTable(
                id = "ask_table",
                columns=[{"name":"Price","id":"price"},{"name":"Quantity","id":"quantity"}],
                style_header = {"display":"none"},
                style_cell = {"minWidth":"140px","maxWidth":"140px","width":"140px",
                    "text-align":"right"}),

                html.H2(id="mid-price", style = {"padding-top":"30px", "text-align":"center"}),

            dash_table.DataTable(
                id = "bid_table",
                columns=[{"name":"Price","id":"price"},{"name":"Quantity","id":"quantity"}],
                style_header = {"display":"none"},
                style_cell = {"minWidth":"140px","maxWidth":"140px","width":"140px",
                                "text-align":"right"}),
            ], style = {"width":"300px"}),

        html.Div(children = [
            dropdown_option("Aggregate Level", options = ["0.01","0.1","1","10","100"],
                default_value = "0.01", _id = "aggregation-level"),
            dropdown_option("Pair", options = ["BTCUSDT","ETHUSDT","SOLUSDT","BDOTDOT"],
                default_value = "ETHUSDT", _id = "pair-select"),
            dropdown_option("Quantity Precision", options = ["0","1","2","3","4"],
                default_value ="2",  _id = "quantity-precision"),
            dropdown_option("Price Precision", options = ["0","1","2","3","4"],
                default_value = "2", _id = "price-precision"),
            ], style = {"padding-left":"100px"}),

        ], style = {"display":"flex",
                    "justify-content":"center",
                    "align-items":"center",
                    "height":"100vh",}),



    dcc.Interval(id="timer", interval=3000),
    ])


def table_styling(df, side):

    if side == "ask":
        bar_color = "rgba(230, 31, 7, 0.2)"
        font_color = "rgb(230, 31, 7)"
    elif side == "bid":
        bar_color = "rgba(13, 230, 49, 0.2)"
        font_color = "rgb(13, 230, 49)"

    n_bins = 25
    bounds = [i * (1.0 / n_bins) for i in range(n_bins + 1)]

    quantity = df.quantity.astype(float)
    ranges = [ ((quantity.max() - quantity.min()) * i) + quantity.min() for i in bounds]

    cell_bg_color = "#060606"

    styles = []

    for i in range(1, len(bounds)):

        min_bound = ranges[i - 1]
        max_bound = ranges[i]
        max_bound_percentage = bounds[i] * 100

        styles.append({

            "if": {
                "filter_query": ("{{quantity}} >= {min_bound}" +
                            (" && {{quantity}} < {max_bound}" if (i < (len(bounds)-1)) else "")
                            ).format(min_bound = min_bound, max_bound=max_bound),
                "column_id":"quantity"
                },
            "background": (
                """
                    linear-gradient(270deg,
                    {bar_color} 0%,
                    {bar_color} {max_bound_percentage}%,
                    {cell_bg_color} {max_bound_percentage}%,
                    {cell_bg_color} 100%)
                """.format(bar_color = bar_color, cell_bg_color = cell_bg_color,
                        max_bound_percentage=max_bound_percentage),
                ),
                "paddingBottom": 2,
                "paddingTop": 2,
                })


    styles.append({
        "if": {"column_id":"price"},
        "color":font_color,
        "background-color":cell_bg_color,
        })

    return styles

def aggregate_levels(levels_df, agg_level = Decimal('1'), side = "bid"):

    if side == "bid":
        right = False
        label_func = lambda x: x.left

    elif side == "ask":
        right = True
        label_func = lambda x: x.right

    min_level =  math.floor(Decimal(min(levels_df.price))/agg_level - 1)*agg_level
    max_level =  math.ceil(Decimal(max(levels_df.price))/agg_level +1 )*agg_level

    level_bounds = [ float(min_level + agg_level*x) for x in 
                            range( int((max_level - min_level) / agg_level) + 1) ] 

    levels_df["bin"] = pd.cut(levels_df.price, bins = level_bounds,
                                precision = 10, right = right)

    levels_df = levels_df.groupby("bin").agg(
            quantity = ("quantity","sum")).reset_index()

    levels_df["price"] = levels_df.bin.apply(label_func)

    levels_df = levels_df[ levels_df.quantity > 0 ]

    levels_df = levels_df[["price", "quantity"]]

    return levels_df


@app.callback(
        Output("bid_table", "data"),
        Output("bid_table", "style_data_conditional"),
        Output("ask_table", "data"),
        Output("ask_table", "style_data_conditional"),
        Output("mid-price", "children"),
        Input("aggregation-level", "value"),
        Input("quantity-precision", "value"),
        Input("price-precision", "value"),
        Input("pair-select", "value"),
        Input("timer", "n_intervals"),
        )
def update_orderbook(agg_level, quantity_precision, price_precision, symbol, n_intervals):

    url = "https://api.binance.com/api/v3/depth"

    levels_to_show = 10

    params = {
            "symbol":symbol.upper(),
            "limit":5000,
            }

    data = requests.get(url, params=params).json()

    bid_df = pd.DataFrame(data["bids"], columns = ["price","quantity"], dtype =float)
    ask_df = pd.DataFrame(data["asks"], columns = ["price","quantity"], dtype =float)

    mid_price = (bid_df.price.iloc[0] + ask_df.price.iloc[0])/2

    mid_price_precision = int(quantity_precision) + 2
    mid_price = f"%.{mid_price_precision}f" % mid_price

    bid_df = aggregate_levels(bid_df, agg_level = Decimal(agg_level), side = "bid")
    bid_df = bid_df.sort_values("price", ascending=False)

    ask_df = aggregate_levels(ask_df, agg_level = Decimal(agg_level), side = "ask")
    ask_df = ask_df.sort_values("price", ascending=False)


    bid_df = bid_df.iloc[:levels_to_show]
    ask_df = ask_df.iloc[-levels_to_show:]

    bid_df.quantity = bid_df.quantity.apply(
            lambda x: f"%.{quantity_precision}f" % x)

    bid_df.price = bid_df.price.apply(
            lambda x: f"%.{price_precision}f" % x)

    ask_df.quantity = ask_df.quantity.apply(
            lambda x: f"%.{quantity_precision}f" % x)

    ask_df.price = ask_df.price.apply(
            lambda x: f"%.{price_precision}f" % x)

    return (bid_df.to_dict("records"), table_styling(bid_df, "bid"),
                ask_df.to_dict("records"), table_styling(ask_df, "ask"), mid_price)

if __name__ == "__main__":
    app.run_server(debug=True)
