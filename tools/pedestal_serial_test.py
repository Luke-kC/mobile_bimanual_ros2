from pedestal_serial import PedestalSerial

PORT = "/dev/serial/by-id/usb-1a86_USB_Serial-if00-port0"


def main() -> None:
    pedestal = PedestalSerial(PORT)

    try:
        while True:
            command = input("> ").strip()

            match command:
                case "u":
                    pedestal.up()
                case "d":
                    pedestal.down()
                case "s":
                    pedestal.stop()
                case "l":
                    pedestal.unlock()
                case "x":
                    break
    finally:
        pedestal.close()


if __name__ == "__main__":
    main()
