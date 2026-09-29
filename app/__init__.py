try:  # .env 에 넣은 인증키를 자동으로 읽는다
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
