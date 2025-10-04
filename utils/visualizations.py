"""
Visualization utilities for the weather app
Using custom color scheme: #00cccb (cyan), #6640b2 (purple), #d8d8d8 (grey)
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Custom color scheme
COLOR_PURPLE = '#6640b2'
COLOR_CYAN = '#00cccb'
COLOR_GREY_BG = '#d8d8d8'
COLOR_WHITE = '#ffffff'


def create_temperature_chart(df, days=7):
    """Create temperature forecast chart"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['DATE'][:days],
        y=df['TEMP'][:days],
        mode='lines+markers',
        name='Temperature',
        line=dict(color=COLOR_CYAN, width=3, shape='spline'),
        marker=dict(size=10, color=COLOR_PURPLE, line=dict(width=2, color=COLOR_WHITE))
    ))
    
    fig.update_layout(
        title="Temperature Forecast",
        xaxis_title="Date",
        yaxis_title="Temperature (°C)",
        plot_bgcolor=COLOR_WHITE,
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE, size=12),
        hovermode='x unified'
    )
    
    return fig


def create_weather_gauge(value, title, range_max=100):
    """Create a gauge chart for weather metrics"""
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': title, 'font': {'color': COLOR_PURPLE, 'size': 16}},
        gauge={
            'axis': {'range': [None, range_max], 'tickcolor': COLOR_PURPLE},
            'bar': {'color': COLOR_CYAN, 'thickness': 0.7},
            'bgcolor': COLOR_WHITE,
            'borderwidth': 2,
            'bordercolor': COLOR_PURPLE,
            'steps': [
                {'range': [0, range_max * 0.33], 'color': '#f0f0f0'},
                {'range': [range_max * 0.33, range_max * 0.67], 'color': '#e0e0e0'},
                {'range': [range_max * 0.67, range_max], 'color': COLOR_GREY_BG}
            ],
        }
    ))
    
    fig.update_layout(
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE),
        height=250
    )
    
    return fig


def create_correlation_heatmap(df):
    """Create correlation heatmap for weather variables"""
    # Select numeric columns
    numeric_cols = ['TEMP', 'HUMIDITY', 'WIND_SPEED', 'SURFACE_PRESSURE', 'LIQUID_WATER']
    corr_matrix = df[numeric_cols].corr()
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=numeric_cols,
        y=numeric_cols,
        colorscale=[[0, COLOR_CYAN], [0.5, COLOR_WHITE], [1, COLOR_PURPLE]],
        zmid=0,
        text=corr_matrix.values.round(2),
        texttemplate='%{text}',
        textfont={"size": 12},
        colorbar=dict(title="Correlation", titleside="right")
    ))
    
    fig.update_layout(
        title="Weather Variables Correlation",
        plot_bgcolor=COLOR_WHITE,
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE),
        xaxis=dict(tickangle=45)
    )
    
    return fig


def create_weather_distribution(df):
    """Create weather type distribution pie chart"""
    # Classify weather types
    def classify_weather(row):
        if row['TEMP'] > 30:
            return 'Hot'
        elif row['TEMP'] < 10:
            return 'Cold'
        elif row['WIND_SPEED'] > 15:
            return 'Windy'
        elif row['HUMIDITY'] > 80:
            return 'Humid'
        else:
            return 'Mild'
    
    df['WEATHER_TYPE'] = df.apply(classify_weather, axis=1)
    weather_counts = df['WEATHER_TYPE'].value_counts()
    
    fig = go.Figure(data=[go.Pie(
        labels=weather_counts.index,
        values=weather_counts.values,
        hole=0.4,
        marker=dict(
            colors=[COLOR_CYAN, COLOR_PURPLE, '#7f8c8d', '#9b59b6', '#00a8a8'],
            line=dict(color=COLOR_WHITE, width=2)
        ),
        textinfo='percent+label',
        textfont=dict(size=14, color=COLOR_WHITE)
    )])
    
    fig.update_layout(
        title="Weather Distribution",
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    
    return fig


def create_rain_probability_chart(forecast_df):
    """Create rain probability bar chart"""
    fig = go.Figure(go.Bar(
        x=forecast_df['Date'],
        y=forecast_df['Rain_Probability'],
        marker=dict(
            color=forecast_df['Rain_Probability'],
            colorscale=[[0, COLOR_GREY_BG], [0.5, COLOR_CYAN], [1, COLOR_PURPLE]],
            line=dict(color=COLOR_PURPLE, width=2)
        ),
        text=forecast_df['Rain_Probability'].round(1).astype(str) + '%',
        textposition='outside',
        hovertemplate='<b>Date:</b> %{x}<br><b>Probability:</b> %{y:.1f}%<extra></extra>'
    ))
    
    fig.update_layout(
        title="7-Day Rain Probability Forecast",
        xaxis_title="Date",
        yaxis_title="Probability (%)",
        plot_bgcolor=COLOR_WHITE,
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE),
        yaxis=dict(range=[0, 100])
    )
    
    return fig


def create_humidity_wind_scatter(df):
    """Create scatter plot of humidity vs wind speed"""
    fig = go.Figure(go.Scatter(
        x=df['HUMIDITY'],
        y=df['WIND_SPEED'],
        mode='markers',
        marker=dict(
            size=8,
            color=df['TEMP'],
            colorscale=[[0, COLOR_CYAN], [0.5, COLOR_GREY_BG], [1, COLOR_PURPLE]],
            showscale=True,
            colorbar=dict(title="Temp (°C)"),
            line=dict(width=1, color=COLOR_PURPLE)
        ),
        text=df['TEMP'].round(1).astype(str) + '°C',
        hovertemplate='<b>Humidity:</b> %{x}%<br><b>Wind:</b> %{y} m/s<br><b>Temp:</b> %{text}<extra></extra>'
    ))
    
    fig.update_layout(
        title="Humidity vs Wind Speed (colored by Temperature)",
        xaxis_title="Humidity (%)",
        yaxis_title="Wind Speed (m/s)",
        plot_bgcolor=COLOR_WHITE,
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE)
    )
    
    return fig


def create_multi_metric_chart(df, days=30):
    """Create multi-line chart for multiple metrics"""
    fig = go.Figure()
    
    # Normalize data for comparison
    df_norm = df.copy()
    metrics = ['TEMP', 'HUMIDITY', 'WIND_SPEED']
    
    for metric in metrics:
        df_norm[f'{metric}_NORM'] = (df[metric] - df[metric].min()) / (
            df[metric].max() - df[metric].min()
        ) * 100
    
    fig.add_trace(go.Scatter(
        x=df['DATE'][:days],
        y=df_norm['TEMP_NORM'][:days],
        mode='lines',
        name='Temperature',
        line=dict(color=COLOR_PURPLE, width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['DATE'][:days],
        y=df_norm['HUMIDITY_NORM'][:days],
        mode='lines',
        name='Humidity',
        line=dict(color=COLOR_CYAN, width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=df['DATE'][:days],
        y=df_norm['WIND_SPEED_NORM'][:days],
        mode='lines',
        name='Wind Speed',
        line=dict(color='#7f8c8d', width=2)
    ))
    
    fig.update_layout(
        title="Weather Metrics Comparison (Normalized)",
        xaxis_title="Date",
        yaxis_title="Normalized Value (0-100)",
        plot_bgcolor=COLOR_WHITE,
        paper_bgcolor=COLOR_GREY_BG,
        font=dict(color=COLOR_PURPLE),
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig
