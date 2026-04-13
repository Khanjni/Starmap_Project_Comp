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


def compute_dominant_vegetation(parks_gdf, vegetation_gdf):
    print("Reprojecting datasets to equal-area CRS...")
    parks_proj = parks_gdf.to_crs(EQUAL_AREA_CRS).copy()
    vegetation_proj = vegetation_gdf.to_crs(EQUAL_AREA_CRS).copy()

    print("Performing spatial intersection...")
    intersections = gpd.overlay(
        parks_proj[["PARK_NAME", "geometry"]],
        vegetation_proj[["VEGDESC", "geometry"]],
        how="intersection"
    )

    if intersections.empty:
        print("No overlaps found. Assigning 'Unknown' to all parks.")
        result = parks_proj.copy()
        result["dominant_vegetation"] = "Unknown"
        return result

    print("Computing overlap areas...")
    intersections["overlap_area"] = intersections.geometry.area

    print("Selecting dominant vegetation for each park...")
    max_overlap_idx = (
        intersections.groupby("PARK_NAME")["overlap_area"]
        .idxmax()
    )

    dominant = intersections.loc[
        max_overlap_idx, ["PARK_NAME", "VEGDESC"]
    ].rename(columns={"VEGDESC": "dominant_vegetation"})

    print("Merging results back to parks dataset...")
    result = parks_proj.merge(
        dominant,
        on="PARK_NAME",
        how="left"
    )

    result["dominant_vegetation"] = result["dominant_vegetation"].fillna("Unknown")

    return result


def main():
    if len(sys.argv) != 4:
        print("Usage: python script.py <parks_geojson> <vegetation_geojson> <output_geojson>")
        sys.exit(1)

    parks_path = sys.argv[1]
    vegetation_path = sys.argv[2]
    output_path = sys.argv[3]

    try:
        parks_gdf = load_and_clean_data(parks_path)
        vegetation_gdf = load_and_clean_data(vegetation_path)

        result = compute_dominant_vegetation(parks_gdf, vegetation_gdf)

        print("Reprojecting output to EPSG:4326...")
        result = result.to_crs(OUTPUT_CRS)

        output_gdf = result[["PARK_NAME", "dominant_vegetation", "geometry"]]

        print(f"Writing output to: {output_path}")
        output_gdf.to_file(output_path, driver="GeoJSON")

        print("Done.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()