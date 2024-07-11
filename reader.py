import csv


def read_csv(filepath: str) -> dict[str, str]:
    result = {}
    with open(filepath, newline="", encoding="utf-8") as file:
        csv_reader = csv.reader(file)
        for row in csv_reader:
            key = row[0]
            result[key] = tuple([i for i in row[1:] if i])

    return result


if __name__ == "__main__":
    filepath = "data.csv"
    key_value_dict = read_csv(filepath)
    for key, value in key_value_dict.items():
        print(f"{key}: {value}")
