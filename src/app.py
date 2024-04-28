import pandas as pd
import numpy as np

import requests
import json

import os

import time
import calendar

from datetime import datetime
from datetime import date, timedelta

import hvplot as hv
import holoviews as hvs
import panel as pn
import hvplot.pandas

from dotenv import load_dotenv

# Specify the path to your .env file
# dotenv_path = '/../.env'
# Polygon_API_Key = os.getenv('Polygon_API_Key') 

Polygon_API_Key = os.environ.get('mypolgonAPI') 

def generate_option_contract_id(ticker, exp_date, option_type, strike_price):
    """
    Generate a concise contract identifier string based on input values.

    Args:
        ticker (str): The stock ticker symbol.
        exp_date (str): The expiration date of the option (format: "YYYY-MM-DD").
        option_type (str): The type of option ("C" for call or "P" for put).
        strike_price (float): The strike price of the option.

    Returns:
        str: The generated option contract identifier string.
    """
    # Format expiration date (remove dashes and take last 6 digits)
    formatted_exp_date = str(exp_date).replace('-', '')[-6:]

    # Format strike price (remove decimal point and zero-pad)
    formatted_strike_price = f"{int(strike_price * 1000):08d}"  # Convert to integer and zero-pad to 5 digits

    # Determine option type label (use uppercase)
    option_label = option_type.upper()

    # Generate the contract identifier string
    contract_id = f"{ticker}{formatted_exp_date}{option_label}{formatted_strike_price}"

    return contract_id  # Ensure the total length does not exceed 11 characters

def extract_raw_data(contract , interval, timeframe, startdate ,enddate):
  url = f"https://api.polygon.io/v2/aggs/ticker/O:{contract}/range/{interval}/{timeframe}/{startdate}/{enddate}?apiKey={Polygon_API_Key}"

  headers={"Authorization": f"Bearer {Polygon_API_Key}"}

  resp = requests.get(url , headers=headers)
  if resp.status_code == 200:
    # print(resp.text)
    if json.loads(resp.text)['resultsCount']>0:
      data = json.loads(resp.text)['results']
      df = pd.DataFrame(data)
      # df['t'] = pd.to_datetime(df['t'], unit='ms')
      df['UNIXTIME'] = pd.to_datetime(df['t'], unit='ms', utc=True).map(lambda x: x.tz_convert('America/New_York'))
      return df
  # print(resp.status_code)
  # raise Exception(f"API request failed with status code: {resp.status_code}")
  return pd.DataFrame() #Empty Dataframe

def _transform_data(raw_data: pd.DataFrame):
    data = raw_data[["UNIXTIME", "o", "h", "l", "c", "v"]].copy(deep=True).rename(columns={
        "UNIXTIME": "time",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
    })
    # data['time_start'] = data.time  # rectangles start (no offset for 1-minute)
    # data['time_end'] = data.time    # rectangles end (no offset for 1-minute)
    # data['positive'] = ((data.close - data.open) > 0).astype(int)
    # return data

    # Calculate delta (minimum difference) between timestamps in seconds
    delta = data['time'].diff().dt.total_seconds().min() /2 # Adjust for missing values if needed

    data['time_start'] = data['time'] - pd.Timedelta(seconds=delta)  # rectangles start (no offset for 1-minute)
    data['time_end'] = data['time'] + pd.Timedelta(seconds=delta)  # rectangles end with delta

    data['positive'] = ((data.close - data.open) > 0).astype(int)
    return data

def get_last_friday():
  today = date.today()
  # Check if today is Friday, if not go back to previous friday
  last_friday = today - timedelta(days = (today.weekday() - calendar.FRIDAY) % 7, weeks=(today.weekday() == calendar.FRIDAY))
  return last_friday


ticker = pn.widgets.AutocompleteInput(name='Ticker', options=['NVDA','TSLA', 'AMZN' , 'MSFT' , 'AAPL' , 'GOOG' , 'AMD'] , placeholder='Write Ticker here همین جا',value='ALL', restrict=False)
ticker.value = "NVDA"

exp_date = pn.widgets.DatePicker(
    name ="Expiry Date",
    description='Select a Date',
    start= date.today() - timedelta(days=365 * 2)
)
exp_date.value = get_last_friday() #date.today() - timedelta(days= 2)

startdate = pn.widgets.DatePicker(
    name ="Start Date",
    description='Select a Date',
    start= date.today() - timedelta(days=365 * 2)
)
startdate.value =  get_last_friday() 


enddate = pn.widgets.DatePicker(
    name ="End Date",
    description='Select a Date',
    start= date.today() - timedelta(days=365 * 2)
)
enddate.value =  get_last_friday() 

option_type = pn.widgets.Select(name='Option Type', options=['C', 'P'])
option_type.value = 'C'

strike_price = pn.widgets.IntInput(name='IntInput', value=850, step=10, start=0, end=1000)

interval = pn.widgets.Select(name='Time Frame (min)', options=['1', '5', '10'])
timeframe = "minute" #The only supported resolutions are minute|hour|day|week|month|quarter|year"0

def make_candle_stick(ticker , exp_date, option_type, strike_price, interval ,startdate , enddate  ):
  contract = generate_option_contract_id(ticker, exp_date, option_type, strike_price)
  raw_data = extract_raw_data(contract , interval, timeframe, startdate ,enddate)
  if raw_data.shape[0]!=0:
    data = _transform_data(raw_data=raw_data)
    _delta = np.median(np.diff(data.time))
    candlestick = hvs.Segments(data, kdims=['time', 'low', 'time', 'high']) * hvs.Rectangles(data, kdims=['time_start','open', 'time_end', 'close'], vdims=['positive'])
    candlestick = candlestick.redim.label(Low='Values')
    candlechart = pn.Column(candlestick.opts(hvs.opts.Rectangles(color='positive', cmap=['red', 'green'], responsive=True), hvs.opts.Segments(color='black', height=800, responsive=True , show_grid=True, title=contract)) ,
                      data.hvplot(x="time", y="volume", kind="line", responsive=True, height=200).opts( show_grid=True) )
                    #  data.hvplot(y="volume", kind="bar", responsive=True, height=200) )
  else:
    candlechart = pn.Column(pn.widgets.LoadingSpinner(value=True, size=20, name='Loading...'))
    # time.sleep(60)
  return candlechart

bound_plot = pn.bind( make_candle_stick, ticker = ticker, exp_date=exp_date , option_type=option_type ,strike_price=strike_price,  interval=interval , startdate=startdate,enddate=enddate)
pn.Row(pn.Column(ticker, exp_date , option_type , strike_price , interval , timeframe , startdate , enddate), bound_plot).servable(title="Intraday Options Price - Pattern Detection")
