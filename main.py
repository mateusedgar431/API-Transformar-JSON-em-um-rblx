from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

SERVICOS_MESTRES = {
    "workspace": "Workspace",
    "lighting": "Lighting",
    "replicatedfirst": "ReplicatedFirst",
    "replicatedstorage": "ReplicatedStorage",
    "serverscriptservice": "ServerScriptService",
    "serverstorage": "ServerStorage",
    "startergui": "StarterGui",
    "starterplayer": "StarterPlayer",
    "starterpack": "StarterPack",
    "teams": "Teams",
    "soundservice": "SoundService",
    "materialservice": "MaterialService",
    "httpservice": "HttpService",
    "testservice": "TestService",
    "voicechatservice": "VoiceChatService",
    "localizationservice": "LocalizationService",
    "chat": "Chat"
}

PROPRIEDADES_PADRAO = {
    "Lighting": {
        "Ambient": {"R": 0.5, "G": 0.5, "B": 0.5},
        "Brightness": 2.0,
        "ClockTime": 14.0,
        "ColorShift_Bottom": {"R": 0.0, "G": 0.0, "B": 0.0},
        "ColorShift_Top": {"R": 0.0, "G": 0.0, "B": 0.0},
        "EnvironmentDiffuseScale": 1.0,
        "EnvironmentSpecularScale": 1.0,
        "ExposureCompensation": 0.0,
        "FogColor": {"R": 0.75, "G": 0.75, "B": 0.75},
        "FogEnd": 100000.0,
        "FogStart": 0.0,
        "GeographicLatitude": 41.73,
        "GlobalShadows": True,
        "OutdoorAmbient": {"R": 0.5, "G": 0.5, "B": 0.5},
        "ShadowSoftness": 0.5,
        "Technology": "ShadowMap"
    },
    "SoundService": {
        "AmbientReverb": "NoReverb",
        "DistanceFactor": 3.33,
        "DopplerScale": 1.0,
        "RespectFilteringEnabled": True
    },
    "StarterGui": {
        "ResetPlayerGuiOnSpawn": True,
        "ScreenOrientation": "LandscapeSensor"
    },
    "StarterPlayer": {
        "CameraMaxZoomDistance": 128.0,
        "CameraMinZoomDistance": 0.5,
        "CameraMode": "Classic",
        "EnableMouseLockOption": True,
        "HealthDisplayDistance": 100.0,
        "NameDisplayDistance": 100.0,
        "UserEmotesEnabled": True
    },
    "HttpService": {"HttpEnabled": False},
    "VoiceChatService": {"EnableDefaultVoice": True},
    "MaterialService": {"Use2022Materials": True},
    "ReplicatedFirst": {},
    "ReplicatedStorage": {},
    "ServerScriptService": {},
    "ServerStorage": {},
    "StarterPack": {},
    "Teams": {},
    "TestService": {},
    "LocalizationService": {},
    "Chat": {}
}

MAPA_ENUM = {
    "Compatibility": 0, "Voxel": 1, "ShadowMap": 2, "Future": 3,
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, 
    "Universal": 5, "Hinge": 6, "Motor": 7, "SteppingMotor": 8,
    "Right": 0, "Top": 1, "Back": 2, "Left": 3, "Bottom": 4, "Front": 5,
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512, "Metal": 1088, "Grass": 1280,
    "Custom": 0, "Scriptable": 1, "Track": 2, "Follow": 3,
    "NoReverb": 0, "Generic": 1000, "PaddedCell": 2000, "Room": 3000, "Bathroom": 4000, "Cave": 8000
}

MAPA_PROPRIEDADES_CANONICAS = {
    "ambient": "Ambient",
    "outdoorambient": "OutdoorAmbient",
    "fogcolor": "FogColor",
    "fogend": "FogEnd",
    "fogstart": "FogStart",
    "brightness": "Brightness",
    "clocktime": "ClockTime",
    "timeofday": "TimeOfDay",
    "technology": "Technology",
    "exposurecompensation": "ExposureCompensation",
    "geographiclatitude": "GeographicLatitude",
    "globalshadows": "GlobalShadows",
    "shadowsoftness": "ShadowSoftness",
    "environmentdiffusescale": "EnvironmentDiffuseScale",
    "environmentspecularscale": "EnvironmentSpecularScale",
    "colorshift_top": "ColorShift_Top",
    "colorshift_bottom": "ColorShift_Bottom"
}

PROPS_FLOAT = {
    "FogEnd", "FogStart", "Brightness", "ClockTime",
    "EnvironmentDiffuseScale", "EnvironmentSpecularScale",
    "ExposureCompensation", "GeographicLatitude", "ShadowSoftness",
    "DistanceFactor", "DopplerScale", "CameraMaxZoomDistance",
    "CameraMinZoomDistance", "HealthDisplayDistance", "NameDisplayDistance",
    "Transparency", "Reflectance", "Volume"
}

def converter_cor(valor):
    """Lê exatamente o formato {R=..., G=..., B=...} gerado pelo limparParaJSON"""
    r, g, b = 0.0, 0.0, 0.0
    if isinstance(valor, dict):
        r = float(valor.get("R", 0.0))
        g = float(valor.get("G", 0.0))
        b = float(valor.get("B", 0.0))
    elif isinstance(valor, (list, tuple)) and len(valor) >= 3:
        r, g, b = float(valor[0]), float(valor[1]), float(valor[2])

    # Normalização automática para escala 0.0 - 1.0 exigida pelo XML
    rf = r / 255.0 if r > 1.0 else r
    gf = g / 255.0 if g > 1.0 else g
    bf = b / 255.0 if b > 1.0 else b

    return rf, gf, bf

def tratar_propriedade_individual(nome_prop_raw, valor, props_dict=None):
    if valor is None or nome_prop_raw in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    nome_prop = MAPA_PROPRIEDADES_CANONICAS.get(str(nome_prop_raw).lower(), nome_prop_raw)

    # 1. TRATAMENTO DE COLORSEQUENCE (Vindo do limparParaJSON)
    if isinstance(valor, list) and len(valor) > 0 and isinstance(valor[0], dict) and "Value" in valor[0]:
        seq_xml = f'<ColorSequence name="{nome_prop}">'
        for kp in valor:
            rf, gf, bf = converter_cor(kp.get("Value", {}))
            t_val = float(kp.get("Time", 0.0))
            seq_xml += f'<ColorSequenceKeypoint time="{t_val}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></ColorSequenceKeypoint>'
        seq_xml += '</ColorSequence>'
        return seq_xml

    # 2. TRATAMENTO DE COLOR3 ({R=..., G=..., B=...})
    if isinstance(valor, dict) and "R" in valor and "G" in valor and "B" in valor:
        rf, gf, bf = converter_cor(valor)
        return f'<Color3 name="{nome_prop}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></Color3>'

    # 3. TRATAMENTO DE VECTOR3 ({X=..., Y=..., Z=...})
    if isinstance(valor, dict) and "X" in valor and "Y" in valor and "Z" in valor and "R00" not in valor:
        return f'<Vector3 name="{nome_prop}"><X>{valor["X"]}</X><Y>{valor["Y"]}</Y><Z>{valor["Z"]}</Z></Vector3>'

    # 4. TRATAMENTO DE UDIM2 ({X={Scale=..., Offset=...}, Y={...}})
    if isinstance(valor, dict) and "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
        x_dict = valor.get("X", {})
        y_dict = valor.get("Y", {})
        return f'''<UDim2 name="{nome_prop}">
            <XS>{x_dict.get("Scale", 0)}</XS><XO>{x_dict.get("Offset", 0)}</XO>
            <YS>{y_dict.get("Scale", 0)}</YS><YO>{y_dict.get("Offset", 0)}</YO>
        </UDim2>'''

    # 5. TRATAMENTO DE CFRAME (Lista enviada pelo GetComponents())
    if nome_prop == "CFrame" or (isinstance(valor, (list, tuple)) and len(valor) >= 12):
        if isinstance(valor, (list, tuple)) and len(valor) >= 12:
            return f'''<CoordinateFrame name="{nome_prop}">
                <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
                <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
                <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
                <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
            </CoordinateFrame>'''

    # Evita duplicação de Position se CFrame estiver presente
    if nome_prop in ["Position", "Orientation", "Rotation"] and props_dict and "CFrame" in props_dict:
        return ""

    if isinstance(valor, bool):
        return f'<bool name="{nome_prop}">{"true" if valor else "false"}</bool>'

    if nome_prop in PROPS_FLOAT:
        try:
            return f'<float name="{nome_prop}">{float(valor)}</float>'
        except (ValueError, TypeError):
            pass

    if nome_prop == "TimeOfDay":
        return f'<string name="TimeOfDay">{saxutils.escape(str(valor))}</string>'

    # Trata Enums em string ("Enum.Material.Plastic" ou "Plastic")
    e_enum = (
        nome_prop in ["Shape", "Font", "PartType", "Face", "NormalId", "Technology", "CameraType", "Material", "AmbientReverb"] or
        nome_prop.endswith("Surface") or nome_prop.endswith("Type") or 
        nome_prop.endswith("Style") or nome_prop.endswith("Mode")
    )
    if e_enum or (isinstance(valor, str) and "Enum." in valor):
        val_clean = str(valor).split(".")[-1]
        token_val = MAPA_ENUM.get(val_clean, val_clean)
        return f'<token name="{nome_prop}">{token_val}</token>'

    if isinstance(valor, float):
        return f'<float name="{nome_prop}">{valor}</float>'

    if isinstance(valor, int):
        return f'<int name="{nome_prop}">{valor}</int>'

    if isinstance(valor, str):
        if nome_prop in ["Texture", "Image", "TextureId", "ImageId", "MeshId", "SoundId"] or valor.startswith("rbxassetid://"):
            return f'<Content name="{nome_prop}"><url>{saxutils.escape(valor)}</url></Content>'
        return f'<string name="{nome_prop}">{saxutils.escape(valor)}</string>'

    return ""

def processar_dicionario_propriedades(props_dict):
    xml_props = ""
    chaves_processadas = set()

    for k, v in props_dict.items():
        k_canonico = MAPA_PROPRIEDADES_CANONICAS.get(str(k).lower(), k)
        if k_canonico in chaves_processadas:
            continue
        chaves_processadas.add(k_canonico)
        
        no_xml = tratar_propriedade_individual(k, v, props_dict)
        if no_xml:
            xml_props += f"\n            {no_xml}"

    return xml_props

def processar_objetos_xml(TableData):
    xml_output = ""
    if isinstance(TableData, list):
        for idx, a in enumerate(TableData):
            if isinstance(a, dict):
                props = a.get("Properties", {})
                children = a.get("Children", []) or a.get("Objects", [])
                script_code = a.get("Script") or (props.get("Source") if isinstance(props, dict) else None)

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                ref_id = f"RBX_OBJ_{idx}_{abs(hash(obj_name))}"

                xml_output += f'\n<Item class="{class_name}" referent="{ref_id}">'
                xml_output += '\n  <Properties>'
                xml_output += f'\n    <string name="Name">{saxutils.escape(str(obj_name))}</string>'
                xml_output += processar_dicionario_propriedades(props)

                if script_code or class_name in ["Script", "LocalScript", "ModuleScript"]:
                    codigo_str = str(script_code) if script_code is not None else ""
                    xml_output += f'\n    <ProtectedString name="Source">{saxutils.escape(codigo_str)}</ProtectedString>'

                xml_output += '\n  </Properties>'

                if children and isinstance(children, list):
                    xml_output += processar_objetos_xml(children)

                xml_output += '\n</Item>'

    return xml_output

def construir_rbxlx_completo(part_data_dict):
    workspace_content = ""
    workspace_props = ""
    servicos_dados_finais = {}

    for s_nome in SERVICOS_MESTRES.values():
        if s_nome != "Workspace":
            servicos_dados_finais[s_nome] = {
                "props": PROPRIEDADES_PADRAO.get(s_nome, {}).copy(),
                "objects": []
            }

    if isinstance(part_data_dict, dict):
        for chave_entrada, servico_dados in part_data_dict.items():
            chave_low = str(chave_entrada).strip().lower()
            servico_oficial = SERVICOS_MESTRES.get(chave_low)

            if not servico_oficial:
                continue

            objetos = []
            propriedades_recebidas = {}

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", []) or servico_dados.get("Children", [])
                if "Properties" in servico_dados and isinstance(servico_dados["Properties"], dict):
                    propriedades_recebidas = servico_dados["Properties"]
                else:
                    propriedades_recebidas = {k: v for k, v in servico_dados.items() if k not in ["Objects", "Children"]}

            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_oficial == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
                workspace_props = processar_dicionario_propriedades(propriedades_recebidas)
            else:
                props_normalizadas = {
                    MAPA_PROPRIEDADES_CANONICAS.get(k.lower(), k): v 
                    for k, v in propriedades_recebidas.items()
                }
                servicos_dados_finais[servico_oficial]["props"].update(props_normalizadas)
                servicos_dados_finais[servico_oficial]["objects"] = objetos

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    outros_servicos_str = ""
    for s_nome, dados in servicos_dados_finais.items():
        ref_servico = f"RBX_SERVICE_{s_nome.upper()}"
        props_xml = processar_dicionario_propriedades(dados["props"])
        objs_xml = processar_objetos_xml(dados["objects"])

        outros_servicos_str += f'''
    <Item class="{s_nome}" referent="{ref_servico}">
        <Properties>
            <string name="Name">{s_nome}</string>{props_xml}
        </Properties>{objs_xml}
    </Item>'''

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>{workspace_props}
        </Properties>
        {workspace_content}
    </Item>{outros_servicos_str}
</roblox>'''

    return rbxlx_str.encode('utf-8')

@app.route('/publicar', methods=['POST'])
def publicar():
    try:
        dados_json = request.json
        api_key = request.headers.get('x-api-key')
        universe_id = request.headers.get('universe-id')
        place_id = request.headers.get('place-id')

        if not api_key or not universe_id or not place_id:
            return jsonify({"erro": "Headers obrigatorios faltando."}), 400

        conteudo_rbxlx = construir_rbxlx_completo(dados_json)

        url_roblox = f"https://apis.roblox.com/universes/v1/{universe_id}/places/{place_id}/versions?versionType=Published"
        headers_roblox = {
            "x-api-key": api_key,
            "Content-Type": "application/xml",
            "User-Agent": "RobloxOpenCloudClient/1.0"
        }

        resposta = requests.post(url_roblox, headers=headers_roblox, data=conteudo_rbxlx)

        return jsonify({
            "status": resposta.status_code,
            "resposta_roblox": resposta.text
        })

    except Exception as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
