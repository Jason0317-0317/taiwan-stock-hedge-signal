from .config import Config
from .data import download_market_data
from .emailing import send_report
from .features import build_features
from .model import train_and_forecast
from .reporting import render_email_html, write_outputs


def main():
    config = Config()
    result = train_and_forecast(build_features(download_market_data(config)), config)
    report = write_outputs(result, config)
    print(report)
    html = render_email_html(result, config)
    print("Email sent." if send_report(f"TSMC 尾部風險預測｜{result.as_of}", report, html) else "Email skipped.")


if __name__ == "__main__":
    main()
