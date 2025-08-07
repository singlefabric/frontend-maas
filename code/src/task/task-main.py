# -*- coding: utf-8 -*-
import uvicorn


def main():
    uvicorn.run("app:app", host="0.0.0.0", port=5004, reload=True)


if __name__ == '__main__':
    main()


