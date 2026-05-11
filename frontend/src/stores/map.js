import { defineStore } from "pinia";
import dataLayerService from '@/services/dataLayerService';

import { Map, Overlay } from "ol";
import TileLayer from 'ol/layer/Tile';
import VectorLayer from "ol/layer/Vector";
import VectorSource from "ol/source/Vector";
import View from 'ol/View.js';
import { OSM, TileWMS } from "ol/source";
import { Draw } from "ol/interaction";
import { GeoJSON} from "ol/format";
import { getArea } from "ol/sphere";
import Feature from "ol/Feature";
import { Polygon } from "ol/geom";
import { Style, Circle as StyleCircle, Fill as StyleFill, Stroke as StyleStroke } from "ol/style";
import ImageLayer from 'ol/layer/Image';
import Static from 'ol/source/ImageStatic';
import { transformExtent } from 'ol/proj';

export default defineStore("map", {
    state: () => ({
        map: null,
        visibleLayers: [],
        draw: {
            interaction: null,
            source: null,
            feature: null,
            measure: {
                tooltip: null,
                tooltipElement: null,
            },
            areaFormatted: null
        }
    }),
    actions: {
        initialize() {
            this.map = new Map({
                target: 'map',
                layers: [
                  new TileLayer({
                    name: "OpenStreetMap",
                    source: new OSM()
                  }),
                ],
                view: new View({
                  center: [2800000, 5750000],
                  zoom: 7.3
                }),
            });
        },
        async addLayer(layerInfo, visible = true) {
            if(!layerInfo)
                return;

            let existingLayer = this.map.getLayers().getArray().find(
                (layerItem) => layerItem.get("id") == layerInfo.id
            );
            if(existingLayer) {
                this.showLayer(layerInfo.id);
                return;
            }

            let dataLayerResponse = await dataLayerService.getDataLayer(layerInfo.id)
    
            if(!dataLayerResponse.success) {
                throw dataLayerResponse?.error ?? "Couldn't retrieve datalayer info"
            }

            if(dataLayerResponse.dataLayer == null) {
                throw "Datalayer not found"
            }

            let layer = null;
            let layerSourceType = dataLayerResponse.dataLayer.geoserver?.layer?.source;
            
            // TODO: Implement other layer source types
            switch (layerSourceType) {
                case "wms":
                    let geoserverUrl = dataLayerResponse.dataLayer.geoserver.url;
                    if (geoserverUrl.includes('geoserver:8080')) {
                        geoserverUrl = '/geoserver';
                    }
                    let wmsSource = new TileWMS({
                        url: geoserverUrl + "/wms",
                        params: {
                            FORMAT: dataLayerResponse.dataLayer.geoserver.layer.format.name,
                            LAYERS: dataLayerResponse.dataLayer.geoserver.layer.name
                        },
                        crossOrigin: 'anonymous'
                    });

                    layer = new TileLayer({
                        type: "tile",
                        opacity: 100,
                        visible: visible,
                        source: wmsSource,
                        custom: true,
                        name: dataLayerResponse.dataLayer.name,
                        id: dataLayerResponse.dataLayer.id
                    })
                    break;
                default:
                    throw "Unknown layer source type";
            }
            
            if(visible == true) {
                this.visibleLayers.push(layerInfo.id);
                this._saveVisibleLayers(); 
            }
            
            this.map.addLayer(layer);
        },
        showLayer(layerId) {
            let existingLayer = this.map.getLayers().getArray().find(
                (layerItem) => layerItem.get("id") == layerId
            );

            if(!existingLayer)
                return;

            existingLayer.setVisible(true);
            this.visibleLayers.push(layerId);
            this._saveVisibleLayers(); 
        },
        hideLayer(layerId) {
            let existingLayer = this.map.getLayers().getArray().find(
                (layerItem) => layerItem.get("id") == layerId
            );

            if(!existingLayer)
                return;

            existingLayer.setVisible(false);
            let indexOfVisibleLayer = this.visibleLayers.indexOf(layerId);

            this.visibleLayers.splice(indexOfVisibleLayer, 1);
            this._saveVisibleLayers();
        },
        addDrawLayer(feature) {
            const fill = new StyleFill({
                color: "rgba(252, 27, 136, 0.6)",
                width: 4,
            });
            
            const stroke = new StyleStroke({
                color: "rgba(252, 27, 236, 0.6)",
                width: 4,
            });
            
            let drawVectorSource = new VectorSource();
            drawVectorSource.addFeature(feature);

            let drawVectorLayer = new VectorLayer({
                source: drawVectorSource,
                id: "DRAW_LAYER",
                zIndex: 10000,
                style: new Style({
                    image: new StyleCircle({
                        fill: fill,
                        stroke: stroke,
                        radius: 6,
                    }),
                    fill: fill,
                    stroke: stroke,
                }),
            });
            this.map.addLayer(drawVectorLayer);
        },
        removeDrawLayer() {
            let existingDrawLayer = this.map.getLayers().getArray().find(
                (layerItem) => layerItem.get("id") == "DRAW_LAYER"
            );

            if(!existingDrawLayer)
                return;

            this.map.removeLayer(existingDrawLayer);
        },
        addVectorLayer(id, coordinates) {
            const polygon = new Polygon([coordinates]);
            const vectorLayer = new VectorLayer({
                source: new VectorSource({
                    features: [
                        new Feature({
                            geometry: polygon
                        })
                    ]
                }),
                id: id,
                zIndex: 20000,
                visible: true,
                style: new Style({
                    fill: new StyleFill({
                        color: "rgba(252, 244, 27, 0.6)",
                    }),
                    stroke: new StyleStroke({
                        color: "rgba(252, 27, 236, 0.6)",
                        width: 2
                    })
                })
            });
            this.map.addLayer(vectorLayer);
        },
        removeVectorLayer(id) {
            let existingLayer = this.map.getLayers().getArray().find(
                (layerItem) => (layerItem.id == id || layerItem.get("id") == id)
            );

            if(!existingLayer)
                return;

            this.map.removeLayer(existingLayer);
        },
        enableDrawInteraction(geometryType = "Polygon", callback = null, measureGeometry = false) {
            const that = this;
            this.draw.source = new VectorSource();
            this.draw.interaction = new Draw({
                source: this.draw.source,
                type: geometryType
            });

            if(measureGeometry) {
                this.createDrawMeasureTooltip();
            }

            this.draw.interaction.on("drawstart", function(event) {
                that.draw.feature = event.feature;
                
                if(measureGeometry) {
                    that.draw.feature.getGeometry().on("change", 
                        function(event) {
                            const geom = event.target;
                            if(geom instanceof Polygon) {
                                that.draw.measure.tooltipElement.innerHTML = that.computeAreaFormatted(geom);
                                let tooltipCoords = geom.getInteriorPoint().getCoordinates();
                                that.draw.measure.tooltip.setPosition(tooltipCoords);
                            } else {
                                throw "Not implemented: measure for another geometry than 'Polygon'.";
                            }
                        }
                    );
                }
            });
            this.draw.interaction.on("drawend", function(event) {
                that.draw.feature = event.feature;

                if(callback) {
                    callback(that.draw.feature);
                }
            });
            this.map.addInteraction(this.draw.interaction);
        },
        disableDrawInteration() {
            if(this.draw.interaction)
                this.map.removeInteraction(this.draw.interaction)
            this.draw.interaction = null;
            this.draw.source = null;
            this.draw.feature = null;
            this.deleteMeasureTooltip();
        },
        createDrawMeasureTooltip() {
            if(this.draw.measure.tooltipElement) {
                this.draw.measure.tooltipElement.remove();
            }
            
            this.draw.measure.tooltipElement = document.createElement("div");
            this.draw.measure.tooltipElement.className = "ol-tooltip ol-tooltip-measure";

            this.draw.measure.tooltip = new Overlay({
                element: this.draw.measure.tooltipElement,
                offset: [0, -15],
                positioning: "bottom-center",
                stopEvent: false,
                insertFirst: false
            });

            this.map.addOverlay(this.draw.measure.tooltip);
        },
        deleteMeasureTooltip() {
            if(this.draw.measure.tooltipElement) {
                this.draw.measure.tooltipElement.remove();
            }
            this.draw.measure.tooltip = null;
            this.draw.measure.tooltipElement = null;
        },
        computeAreaFormatted(polygon) {
            const area = getArea(polygon);
            let output;
            if (area > 10000) {
                output = Math.round((area / 1000000) * 100) / 100 + ' ' + 'km<sup>2</sup>';
            } else {
                output = Math.round(area * 100) / 100 + ' ' + 'm<sup>2</sup>';
            }
            return output;
        },
        getGeoJsonFromFeature(feature, targetCrs = null) {
            let featuresArray = [];
            let featureGeometry = feature.getGeometry().clone();
            
            if(targetCrs) {
                featureGeometry = featureGeometry.transform("EPSG:3857", targetCrs)
            }
            
            featuresArray.push(new Feature(featureGeometry));

            let geoJsonString = new GeoJSON().writeFeatures(featuresArray);
            let geoJson = JSON.parse(geoJsonString);

            return geoJson;
        },
        _saveVisibleLayers() {
            try {
                localStorage.setItem('gfc_visible_layers', JSON.stringify(this.visibleLayers));
            } catch (e) {
                console.warn('Could not save visible layers:', e);
            }
        },

        async restoreVisibleLayers() {
            try {
                const saved = localStorage.getItem('gfc_visible_layers');
                if (!saved) return;
                
                const layerIds = JSON.parse(saved);
                for (const layerId of layerIds) {
                    try {
                        await this.addLayer({ id: layerId }, true);
                    } catch (e) {
                        console.warn(`Could not restore layer ${layerId}:`, e);
                    }
                }
            } catch (e) {
                console.warn('Could not restore visible layers:', e);
            }
        },
         addImageLayer(id, imageUrl, bbox) {
            const extent = transformExtent(bbox, 'EPSG:4326', 'EPSG:3857');
            
            const imageLayer = new ImageLayer({
                id: id,
                source: new Static({
                    url: imageUrl,
                    imageExtent: extent,
                    crossOrigin: 'anonymous'
                }),
                opacity: 0.85,
                zIndex: 15000
            });
            
            this.map.addLayer(imageLayer);
        },
        removeAllOverlays() {
                const layers = this.map.getLayers().getArray().slice();
                for (const layer of layers) {
                    const name = layer.get('name');
                    const id = layer.get('id') || layer.id;
                    // Păstrează doar OSM și layerele din datasets (cu custom: true)
                    if (name === 'OpenStreetMap') continue;
                    if (layer.get('custom') === true) continue;
                    this.map.removeLayer(layer);
                }
        },
    }
})