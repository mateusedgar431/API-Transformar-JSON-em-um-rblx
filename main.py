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
        "Ambient": [0.5, 0.5, 0.5],
        "Brightness": 2.0,
        "ClockTime": 14.0,
        "ColorShift_Bottom": [0.0, 0.0, 0.0],
        "ColorShift_Top": [0.0, 0.0, 0.0],
        "EnvironmentDiffuseScale": 1.0,
        "EnvironmentSpecularScale": 1.0,
        "ExposureCompensation": 0.0,
        "FogColor": [0.75, 0.75, 0.75],
        "FogEnd": 100000.0,
        "FogStart": 0.0,
        "GeographicLatitude": 41.73,
        "GlobalShadows": True,
        "OutdoorAmbient": [0.5, 0.5, 0.5],
        "ShadowSoftness": 0.5,
        "Technology": 2
    },
    "SoundService": {
        "AmbientReverb": 0,
        "DistanceFactor": 3.33,
        "DopplerScale": 1.0,
        "RespectFilteringEnabled": True
    },
    "StarterGui": {
        "ResetPlayerGuiOnSpawn": True,
        "ScreenOrientation": 0
    },
    "StarterPlayer": {
        "CameraMaxZoomDistance": 128.0,
        "CameraMinZoomDistance": 0.5,
        "CameraMode": 0,
        "EnableMouseLockOption": True,
        "HealthDisplayDistance": 100.0,
        "NameDisplayDistance": 100.0,
        "UserEmotesEnabled": True
    },
    "HttpService": {
        "HttpEnabled": False
    },
    "VoiceChatService": {
        "EnableDefaultVoice": True
    },
    "MaterialService": {
        "Use2022Materials": True
    },
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

PROPS_COR = {
    "Ambient", "OutdoorAmbient", "FogColor", "Color",
    "ColorShift_Bottom", "ColorShift_Top", "Color3"
}

CORES_NOMEADAS = {
    "preto": (0.0, 0.0, 0.0),
    "black": (0.0, 0.0, 0.0),
    "branco": (255.0, 255.0, 255.0),
    "white": (255.0, 255.0, 255.0),
    "vermelho": (255.0, 0.0, 0.0),
    "red": (255.0, 0.0, 0.0),
    "verde": (0.0, 255.0, 0.0),
    "green": (0.0, 255.0, 0.0),
    "azul": (0.0, 0.0, 255.0),
    "blue": (0.0, 0.0, 255.0)
}

def converter_para_cor_xml(nome_prop, valor):
    r, g, b = 0.0, 0.0, 0.0

    if isinstance(valor, (list, tuple)) and len(valor) >= 3:
        r, g, b = valor[0], valor[1], valor[2]
    elif isinstance(valor, dict):
        r = valor.get("R", valor.get("r", 0.0))
        g = valor.get("G", valor.get("g", 0.0))
        b = valor.get("B", valor.get("b", 0.0))
    elif isinstance(valor, str):
        v_clean = valor.strip().lower()
        if v_clean in CORES_NOMEADAS:
            r, g, b = CORES_NOMEADAS[v_clean]
        elif v_clean.startswith("#") and len(v_clean) == 7:
            try:
                r = int(v_clean[1:3], 16)
                g = int(v_clean[3:5], 16)
                b = int(v_clean[5:7], 16)
            except ValueError:
                pass

    rf = float(r) / 255.0 if float(r) > 1.0 else float(r)
    gf = float(g) / 255.0 if float(g) > 1.0 else float(g)
    bf = float(b) / 255.0 if float(b) > 1.0 else float(b)

    return f'<Color3 name="{nome_prop}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></Color3>'

def gerar_cframe_xml(nome_prop, valor):
    x, y, z = 0.0, 0.0, 0.0
    r00, r01, r02 = 1.0, 0.0, 0.0
    r10, r11, r12 = 0.0, 1.0, 0.0
    r20, r21, r22 = 0.0, 0.0, 1.0

    if isinstance(valor, (list, tuple)):
        if len(valor) >= 12:
            x, y, z = float(valor[0]), float(valor[1]), float(valor[2])
            r00, r01, r02 = float(valor[3]), float(valor[4]), float(valor[5])
            r10, r11, r12 = float(valor[6]), float(valor[7]), float(valor[8])
            r20, r21, r22 = float(valor[9]), float(valor[10]), float(valor[11])
        elif len(valor) >= 3:
            x, y, z = float(valor[0]), float(valor[1]), float(valor[2])
    elif isinstance(valor, dict):
        x = float(valor.get("X", 0.0))
        y = float(valor.get("Y", 0.0))
        z = float(valor.get("Z", 0.0))

    return f'''<CoordinateFrame name="{nome_prop}">
        <X>{x}</X><Y>{y}</Y><Z>{z}</Z>
        <R00>{r00}</R00><R01>{r01}</R01><R02>{r02}</R02>
        <R10>{r10}</R10><R11>{r11}</R11><R12>{r12}</R12>
        <R20>{r20}</R20><R21>{r21}</R21><R22>{r22}</R22>
    </CoordinateFrame>'''

def tratar_propriedade_individual(nome_prop_raw, valor, props_dict=None):
    if valor is None or nome_prop_raw in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    nome_prop = MAPA_PROPRIEDADES_CANONICAS.get(str(nome_prop_raw).lower(), nome_prop_raw)

    # Trata cores enviadas como dicionario ou lista
    if nome_prop in PROPS_COR or nome_prop.endswith("Color"):
        return converter_para_cor_xml(nome_prop, valor)

    # Trata ColorSequence vindo do Luau
    if isinstance(valor, list) and len(valor) > 0 and isinstance(valor[0], dict) and "Value" in valor[0]:
        seq_xml = f'<ColorSequence name="{nome_prop}">'
        for kp in valor:
            val_cor = kp.get("Value", {})
            r, g, b = 0.0, 0.0, 0.0
            if isinstance(val_cor, dict):
                r = val_cor.get("R", val_cor.get("r", 0.0))
                g = val_cor.get("G", val_cor.get("g", 0.0))
                b = val_cor.get("B", val_cor.get("b", 0.0))
            elif isinstance(val_cor, (list, tuple)) and len(val_cor) >= 3:
                r, g, b = val_cor[0], val_cor[1], val_cor[2]
            
            rf = float(r) / 255.0 if float(r) > 1.0 else float(r)
            gf = float(g) / 255.0 if float(g) > 1.0 else float(g)
            bf = float(b) / 255.0 if float(b) > 1.0 else float(b)
            
            t_val = kp.get("Time", 0.0)
            seq_xml += f'<ColorSequenceKeypoint time="{t_val}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></ColorSequenceKeypoint>'
        seq_xml += '</ColorSequence>'
        return seq_xml

    if nome_prop == "CFrame":
        return gerar_cframe_xml("CFrame", valor)

    if nome_prop in ["Position", "Orientation", "Rotation"] and props_dict and "CFrame" in props_dict:
        return ""

    if nome_prop == "Position" and props_dict and "CFrame" not in props_dict:
        xml_pos = ""
        if isinstance(valor, (list, tuple)) and len(valor) == 3:
            xml_pos = f'<Vector3 name="Position"><X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z></Vector3>\n            '
        elif isinstance(valor, dict) and "X" in valor and "Y" in valor and "Z" in valor:
            xml_pos = f'<Vector3 name="Position"><X>{valor["X"]}</X><Y>{valor["Y"]}</Y><Z>{valor["Z"]}</Z></Vector3>\n            '
        return xml_pos + gerar_cframe_xml("CFrame", valor)

    if isinstance(valor, bool):
        return f'<bool name="{nome_prop}">{"true" if valor else "false"}</bool>'

    if nome_prop in PROPS_FLOAT:
        try:
            val_float = float(valor)
            return f'<float name="{nome_prop}">{val_float}</float>'
        except (ValueError, TypeError):
            pass

    if nome_prop == "TimeOfDay":
        return f'<string name="TimeOfDay">{saxutils.escape(str(valor))}</string>'

    if isinstance(valor, dict):
        if "R" in valor and "G" in valor and "B" in valor:
            return converter_para_cor_xml(nome_prop, valor)

        if "X" in valor and "Y" in valor and "Z" in valor and "R00" not in valor:
            return f'<Vector3 name="{nome_prop}"><X>{valor["X"]}</X><Y>{valor["Y"]}</Y><Z>{valor["Z"]}</Z></Vector3>'

        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
            x_dict, y_dict = valor.get("X", {}), valor.get("Y", {})
            return f'''<UDim2 name="{nome_prop}">
                <XS>{x_dict.get("Scale", 0)}</XS><XO>{x_dict.get("Offset", 0)}</XO>
                <YS>{y_dict.get("Scale", 0)}</YS><YO>{y_dict.get("Offset", 0)}</YO>
            </UDim2>'''

    if isinstance(valor, (list, tuple)):
        if len(valor) == 3:
            return f'<Vector3 name="{nome_prop}"><X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z></Vector3>'
        elif len(valor) == 4 and nome_prop in ["Position", "Size", "AnchorPoint"]:
            return f'''<UDim2 name="{nome_prop}">
                <XS>{valor[0]}</XS><XO>{valor[1]}</XO>
                <YS>{valor[2]}</YS><YO>{valor[3]}</YO>
            </UDim2>'''

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
