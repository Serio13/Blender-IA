// Pirate Prop Forge - importacion automatica para URP (Unity 6).
//
// Instalacion: copia este archivo a Assets/Editor/ de tu proyecto (crea la carpeta Editor si no existe).
// Uso: arrastra A UNIDAD LA CARPETA COMPLETA del asset (con el .fbx, el _report.json y Textures/) a Assets/.
//
// Que hace:
//   1. Marca las texturas segun su nombre: *_Normal.png -> Normal map; *_MetallicSmoothness.png -> sin sRGB.
//   2. Al entrar un .fbx con su _report.json al lado, crea Materials/M_<Asset>.mat (Universal Render Pipeline/Lit),
//      le asigna BaseMap, Normal, Metallic+Smoothness y Emission, y lo asigna al modelo.
//
// Nota: escrito sin poder compilarlo en Unity. Si te da un error de compilacion, borra el archivo y avisa.
using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace PropForge
{
    public class PropForgePostprocessor : AssetPostprocessor
    {
        const string ReportSuffix = "_report.json";

        // Con un mapa Metallic+Smoothness, URP/Lit MULTIPLICA el smoothness del alfa por el slider "Smoothness".
        // 0.5 es el valor por defecto de URP/Lit y el que suele usarse; con 1.0 los aros y la madera salen mas
        // brillantes que en el original. Se aplica solo al CREAR el material: despues ajusta el slider a mano.
        const float DefaultSmoothness = 0.5f;

        void OnPreprocessTexture()
        {
            var importer = (TextureImporter)assetImporter;
            string name = Path.GetFileNameWithoutExtension(assetPath);
            if (name.EndsWith("_Normal", StringComparison.Ordinal))
            {
                importer.textureType = TextureImporterType.NormalMap;
            }
            else if (name.EndsWith("_MetallicSmoothness", StringComparison.Ordinal))
            {
                importer.sRGBTexture = false;
                importer.alphaSource = TextureImporterAlphaSource.FromInput;
                importer.alphaIsTransparency = false;
            }
        }

        static void OnPostprocessAllAssets(string[] imported, string[] deleted, string[] moved, string[] movedFrom)
        {
            foreach (string path in imported)
            {
                string fbx = FindPackageFbx(path);
                if (fbx == null) continue;
                string captured = fbx;
                EditorApplication.delayCall += () => SetupAsset(captured);
            }
        }

        // Devuelve la ruta del .fbx del paquete al que pertenece "path" (el propio fbx o una textura), o null.
        static string FindPackageFbx(string path)
        {
            string dir = Path.GetDirectoryName(path).Replace('\\', '/');
            if (path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase))
            {
                string report = dir + "/" + Path.GetFileNameWithoutExtension(path) + ReportSuffix;
                return File.Exists(report) ? path : null;
            }
            if (path.EndsWith(".png", StringComparison.OrdinalIgnoreCase) && dir.EndsWith("/Textures", StringComparison.Ordinal))
            {
                string packageDir = dir.Substring(0, dir.Length - "/Textures".Length);
                string asset = Path.GetFileName(packageDir);
                string fbx = packageDir + "/" + asset + ".fbx";
                return File.Exists(fbx) && File.Exists(packageDir + "/" + asset + ReportSuffix) ? fbx : null;
            }
            return null;
        }

        static Texture2D LoadTexture(string dir, string asset, string kind)
        {
            return AssetDatabase.LoadAssetAtPath<Texture2D>(dir + "/Textures/" + asset + "_" + kind + ".png");
        }

        static void SetupAsset(string fbxPath)
        {
            string dir = Path.GetDirectoryName(fbxPath).Replace('\\', '/');
            string asset = Path.GetFileNameWithoutExtension(fbxPath);

            Shader shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
            {
                Debug.LogWarning("PropForge: no se encontro 'Universal Render Pipeline/Lit'. Comprueba que URP esta instalado.");
                return;
            }

            string materialsFolder = dir + "/Materials";
            if (!AssetDatabase.IsValidFolder(materialsFolder)) AssetDatabase.CreateFolder(dir, "Materials");
            string matPath = materialsFolder + "/M_" + asset + ".mat";
            Material mat = AssetDatabase.LoadAssetAtPath<Material>(matPath);
            bool created = mat == null;
            if (created)
            {
                mat = new Material(shader);
                AssetDatabase.CreateAsset(mat, matPath);
            }
            else
            {
                mat.shader = shader;
            }

            Texture2D baseMap = LoadTexture(dir, asset, "BaseMap");
            Texture2D normal = LoadTexture(dir, asset, "Normal");
            Texture2D metalSmooth = LoadTexture(dir, asset, "MetallicSmoothness");
            Texture2D emission = LoadTexture(dir, asset, "Emission");

            if (baseMap != null)
            {
                mat.SetTexture("_BaseMap", baseMap);
                mat.SetColor("_BaseColor", Color.white);
            }
            if (normal != null)
            {
                mat.SetTexture("_BumpMap", normal);
                mat.SetFloat("_BumpScale", 1f);
                mat.EnableKeyword("_NORMALMAP");
            }
            if (metalSmooth != null)
            {
                mat.SetTexture("_MetallicGlossMap", metalSmooth);
                if (created) mat.SetFloat("_Smoothness", DefaultSmoothness); // no pisa los ajustes manuales posteriores
                mat.SetFloat("_SmoothnessTextureChannel", 0f); // 0 = alfa del mapa Metallic
                mat.EnableKeyword("_METALLICSPECGLOSSMAP");
            }
            if (emission != null)
            {
                mat.SetTexture("_EmissionMap", emission);
                mat.SetColor("_EmissionColor", Color.white);
                mat.EnableKeyword("_EMISSION");
            }
            EditorUtility.SetDirty(mat);
            AssetDatabase.SaveAssets();

            var importer = AssetImporter.GetAtPath(fbxPath) as ModelImporter;
            if (importer == null) return;
            var id = new AssetImporter.SourceAssetIdentifier(typeof(Material), "M_" + asset);
            var map = importer.GetExternalObjectMap();
            UnityEngine.Object current;
            if (!map.TryGetValue(id, out current) || current != mat)
            {
                importer.AddRemap(id, mat);
                importer.SaveAndReimport();
            }
        }
    }
}
