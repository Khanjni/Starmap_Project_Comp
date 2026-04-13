import sys
import geopandas as gpd

EQUAL_AREA_CRS = "EPSG:3310"
OUTPUT_CRS = "EPSG:4326"

def load_and_clean_data(filepath):
    print(f"Loading: {filepath}")
    gdf = gpd.read_file(filepath)
    if gdf.empty:
        print(f"Warning: {filepath} is empty")
        return gdf
    if gdf.crs is None:
        raise ValueError(f"Input file {filepath} has no CRS defined.")
    print(f"Cleaning geometries for: {filepath}")
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].buffer(0)
    gdf = gdf[gdf.geometry.notnull()]
    gdf = gdf[gdf.is_valid]
    return gdf

def compute_dominant_crop(watersheds_gdf, crops_gdf):
    print("Reprojecting datasets to equal-area CRS...")
    watersheds_proj = watersheds_gdf.to_crs(EQUAL_AREA_CRS).copy()
    crops_proj = crops_gdf.to_crs(EQUAL_AREA_CRS).copy()

    print("Performing spatial intersection...")
    intersections = gpd.overlay(
        watersheds_proj[["watershed_name", "regional_basin", "watershed_acres", "geometry"]],
        crops_proj[["class_name", "acres", "geometry"]],
        how="intersection"
    )

    if intersections.empty:
        print("No overlaps found.")
        result = watersheds_proj.copy()
        result["dominant_crop"] = "Unknown"
        result["dominant_crop_acres"] = 0
        return result

    print("Summing acreage per crop per watershed...")
    crop_totals = (
        intersections.groupby(["watershed_name", "class_name"])["acres"]
        .sum()
        .reset_index()
    )

    print("Finding dominant crop per watershed...")
    idx = crop_totals.groupby("watershed_name")["acres"].idxmax()
    dominant = crop_totals.loc[idx, ["watershed_name", "class_name", "acres"]].rename(
        columns={"class_name": "dominant_crop", "acres": "dominant_crop_acres"}
    )
    dominant["dominant_crop_acres"] = dominant["dominant_crop_acres"].round(2)

    print("Merging results back to watersheds...")
    result = watersheds_proj.merge(dominant, on="watershed_name", how="left")
    result["dominant_crop"] = result["dominant_crop"].fillna("Unknown")
    result["dominant_crop_acres"] = result["dominant_crop_acres"].fillna(0)

    return result

def main():
    if len(sys.argv) != 4:
        print("Usage: python task3_dominant_crop.py <watersheds.geojson> <crops.geojson> <output.geojson>")
        sys.exit(1)

    watersheds_path = sys.argv[1]
    crops_path = sys.argv[2]
    output_path = sys.argv[3]

    try:
        watersheds_gdf = load_and_clean_data(watersheds_path)
        crops_gdf = load_and_clean_data(crops_path)

        result = compute_dominant_crop(watersheds_gdf, crops_gdf)

        print("Reprojecting output to EPSG:4326...")
        result = result.to_crs(OUTPUT_CRS)

        output_gdf = result[["watershed_name", "regional_basin", "watershed_acres", "dominant_crop", "dominant_crop_acres", "geometry"]]

        print(f"Writing output to: {output_path}")
        output_gdf.to_file(output_path, driver="GeoJSON")
        print("Done.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
