def run():
    from . import __main__  # which exec()s the pyang script

    # then manually run the pyang script's run function
    # which is only run automatically if __file__ == '__main__'
    # but now __main__.__file__ == 'yang2adonis.__main__'
    __main__.run()
