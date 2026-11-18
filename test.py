from tools import get_agenda_for_date, generate_image

if __name__ == "__main__":
    generate_image(get_agenda_for_date("today"))