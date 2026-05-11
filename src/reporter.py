import pandas as pd


def write_results(
    implant_records: list[dict],
    interimplant_records: list[dict],
    implant_csv: str,
    interimplant_csv: str,
) -> None:
    implant_df = pd.DataFrame(implant_records)
    interimplant_df = pd.DataFrame(interimplant_records)

    implant_df.to_csv(implant_csv, index=False)
    interimplant_df.to_csv(interimplant_csv, index=False)

    print(f"\nResults written:")
    print(f"  {implant_csv}  ({len(implant_df)} rows)")
    print(f"  {interimplant_csv}  ({len(interimplant_df)} rows)")
