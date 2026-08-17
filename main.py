from flask import Flask, request, jsonify
import requests
import xml.sax.saxutils as saxutils

app = Flask(__name__)

# Mapeamento oficial de serviços (sem Players e sem TextChatService)
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

MAPA_ENUM = {
    "Compatibility": 0, "ShadowMap": 1, "Future": 2, "Voxel": 3,
    "Smooth": 0, "Glue": 1, "Weld": 2, "Studs": 3, "Inlet": 4, 
    "Universal": 5, "Hinge": 6, "Motor": 7, "SteppingMotor": 8,
    "Right": 0, "Top": 1, "Back": 2, "Left": 3, "Bottom": 4, "Front": 5,
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512, "Metal": 1088, "Grass": 1280,
    "Custom": 0, "Scriptable": 1, "Track": 2, "Follow": 3,
    "NoReverb": 0, "Generic": 1000, "PaddedCell": 2000, "Room": 3000, "Bathroom": 4000, "Cave": 8000
}

def converter_para_cor_xml(nome_prop, r, g, b):
    rf = r / 255.0 if r > 1.0 else float(r)
    gf = g / 255.0 if g > 1.0 else float(g)
    bf = b / 255.0 if b > 1.0 else float(b)
    return f'<Color3 name="{nome_prop}"><R>{rf}</R><G>{gf}</G><B>{bf}</B></Color3>'

def tratar_propriedade_individual(nome_prop, valor, props_dict=None):
    if valor is None or nome_prop in ["ClassName", "Name", "Parent", "FormFactor"]:
        return ""

    if props_dict and "CFrame" in props_dict and nome_prop in ["Position", "Orientation", "Rotation"]:
        return ""

    if nome_prop == "CFrame" and isinstance(valor, (list, tuple)) and len(valor) >= 12:
        return f'''<CoordinateFrame name="CFrame">
            <X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z>
            <R00>{valor[3]}</R00><R01>{valor[4]}</R01><R02>{valor[5]}</R02>
            <R10>{valor[6]}</R10><R11>{valor[7]}</R11><R12>{valor[8]}</R12>
            <R20>{valor[9]}</R20><R21>{valor[10]}</R21><R22>{valor[11]}</R22>
        </CoordinateFrame>'''

    if nome_prop == "ClockTime":
        horas = float(valor)
        h = int(horas)
        m = int((horas - h) * 60)
        s = int((((horas - h) * 60) - m) * 60)
        return f'<string name="TimeOfDay">{h:02d}:{m:02d}:{s:02d}</string>'

    if nome_prop == "TimeOfDay":
        return f'<string name="TimeOfDay">{saxutils.escape(str(valor))}</string>'

    if isinstance(valor, bool):
        return f'<bool name="{nome_prop}">{"true" if valor else "false"}</bool>'

    if isinstance(valor, dict):
        if "R" in valor and "G" in valor and "B" in valor:
            return converter_para_cor_xml(nome_prop, valor["R"], valor["G"], valor["B"])

        if "X" in valor and "Y" in valor and "Z" in valor:
            return f'<Vector3 name="{nome_prop}"><X>{valor["X"]}</X><Y>{valor["Y"]}</Y><Z>{valor["Z"]}</Z></Vector3>'

        if "X" in valor and "Y" in valor and isinstance(valor.get("X"), dict):
            x_dict, y_dict = valor.get("X", {}), valor.get("Y", {})
            return f'''<UDim2 name="{nome_prop}">
                <XS>{x_dict.get("Scale", 0)}</XS><XO>{x_dict.get("Offset", 0)}</XO>
                <YS>{y_dict.get("Scale", 0)}</YS><YO>{y_dict.get("Offset", 0)}</YO>
            </UDim2>'''

    if isinstance(valor, (list, tuple)) and len(valor) == 3:
        if nome_prop in ["Ambient", "OutdoorAmbient", "FogColor", "Color", "ColorShift_Bottom", "ColorShift_Top"]:
            return converter_para_cor_xml(nome_prop, valor[0], valor[1], valor[2])
        return f'<Vector3 name="{nome_prop}"><X>{valor[0]}</X><Y>{valor[1]}</Y><Z>{valor[2]}</Z></Vector3>'

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

    if "ClockTime" in props_dict and "TimeOfDay" in props_dict:
        chaves_processadas.add("TimeOfDay")

    for k, v in props_dict.items():
        if k in chaves_processadas:
            continue
        chaves_processadas.add(k)
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
                script_code = a.get("Script") or props.get("Source")

                if not isinstance(props, dict):
                    props = {}

                class_name = props.get("ClassName", "Part")
                obj_name = props.get("Name", f"Object_{idx}")

                if class_name in ["Part", "WedgePart", "CornerWedgePart", "MeshPart", "SpawnLocation", "BasePart"]:
                    if "Anchored" not in props:
                        props["Anchored"] = True

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
    servicos_xml = {s_nome: {"props": "", "objects": ""} for s_nome in SERVICOS_MESTRES.values() if s_nome != "Workspace"}

    if isinstance(part_data_dict, dict):
        for chave_entrada, servico_dados in part_data_dict.items():
            chave_low = str(chave_entrada).strip().lower()
            servico_oficial = SERVICOS_MESTRES.get(chave_low)

            objetos = []
            propriedades_servico = {}

            if isinstance(servico_dados, dict):
                objetos = servico_dados.get("Objects", []) or servico_dados.get("Children", [])
                propriedades_servico = servico_dados.get("Properties", {})
            elif isinstance(servico_dados, list):
                objetos = servico_dados

            if servico_oficial == "Workspace":
                workspace_content += processar_objetos_xml(objetos)
            elif servico_oficial:
                servicos_xml[servico_oficial] = {
                    "props": processar_dicionario_propriedades(propriedades_servico),
                    "objects": processar_objetos_xml(objetos)
                }

    elif isinstance(part_data_dict, list):
        workspace_content = processar_objetos_xml(part_data_dict)

    outros_servicos_str = ""
    for s_nome in SERVICOS_MESTRES.values():
        if s_nome == "Workspace":
            continue

        dados = servicos_xml.get(s_nome, {"props": "", "objects": ""})
        ref_servico = f"RBX_SERVICE_{s_nome.upper()}"

        outros_servicos_str += f'''
    <Item class="{s_nome}" referent="{ref_servico}">
        <Properties>
            <string name="Name">{s_nome}</string>{dados["props"]}
        </Properties>{dados["objects"]}
    </Item>'''

    rbxlx_str = f'''<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://www.roblox.com/roblox.xsd" version="4">
    <External>null</External>
    <External>nil</External>
    <Item class="Workspace" referent="RBX_WORKSPACE_ROOT">
        <Properties>
            <string name="Name">Workspace</string>
            <bool name="FilteringEnabled">true</bool>
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
